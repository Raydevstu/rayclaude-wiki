"""Background runs: start, poll, stream progress (from the evidence ledger) and cancel."""
from __future__ import annotations
import asyncio, time, uuid

from .verification import evaluate_acceptance

MAX_ACTIVE, KEEP = 20, 200


class TaskLimit(Exception):
    pass


class Tasks:
    def __init__(self, modes, store):
        self.modes, self.store, self.t = modes, store, {}

    def _persist(self, rec, event: str):
        body = {key: value for key, value in rec.items() if key != "task"}
        self.store.task_put(rec["id"], rec["status"], body)
        self.store.task_event_add(rec["id"], event, {"status": rec["status"], "progress": rec["progress"]})

    def start(self, prompt: str, mode=None, tier=None, max_cost_usd=None, timeout_s: float = 300, acceptance=None) -> str:
        if sum(1 for x in self.t.values() if x["status"] == "running") >= MAX_ACTIVE:
            raise TaskLimit("too many active tasks")
        tid = uuid.uuid4().hex[:12]
        timeout_s = max(1.0, min(float(timeout_s), 3600.0))
        rec = {"id": tid, "status": "running", "ts": time.time(), "result": None, "error": "",
               "progress": 5, "timeout_s": timeout_s, "acceptance": acceptance,
               "prompt": prompt, "mode": mode, "tier": tier, "max_cost_usd": max_cost_usd, "retry_of": None}
        rec["task"] = asyncio.create_task(self._go(rec, prompt, mode, tier, max_cost_usd, timeout_s, acceptance))
        self.t[tid] = rec
        self._persist(rec, "queued")
        for k in sorted(self.t, key=lambda k: self.t[k]["ts"])[:-KEEP]:       # bounded memory
            if self.t[k]["status"] != "running":
                del self.t[k]
        return tid

    async def _go(self, rec, prompt, mode, tier, max_cost_usd=None, timeout_s=300, acceptance=None):
        try:
            rec["progress"] = 10
            self._persist(rec, "started")
            rec["result"] = await asyncio.wait_for(
                self.modes.run(prompt, mode=mode, tier=tier, trigger=f"async:{rec['id']}",
                               max_cost_usd=max_cost_usd), timeout=timeout_s)
            verification = evaluate_acceptance(str(rec["result"].get("answer", "")), acceptance)
            rec["result"]["verification"] = verification
            rec["progress"] = 100
            rec["status"] = "done" if verification["status"] != "failed_verification" else "failed_verification"
            self.store.ledger_append(rec["result"].get("run_id", rec["id"]), "task_verification", verification)
            self._persist(rec, "completed")
        except asyncio.TimeoutError:
            rec["status"], rec["error"], rec["progress"] = "timeout", f"task exceeded {timeout_s:.1f}s", 100
            self._close_runs(rec["id"], "timeout")
            self._persist(rec, "timeout")
        except asyncio.CancelledError:
            rec["status"], rec["progress"] = "cancelled", 100
            self._close_runs(rec["id"], "cancelled")
            self._persist(rec, "cancelled")
        except Exception as e:
            rec["status"], rec["error"], rec["progress"] = "failed", f"{type(e).__name__}: {e}"[:300], 100
            self._persist(rec, "failed")

    def _close_runs(self, tid: str, status: str):
        for r in self.store.q("SELECT id FROM runs WHERE trigger LIKE ? AND status='running'", (f"async:{tid}%",)):
            self.store.ledger_append(r["id"], f"run_{status}", {})
            self.store.run_finish(r["id"], status, {"status": status})

    def get(self, tid: str):
        live = self.t.get(tid)
        if live:
            return live
        stored = self.store.task_get(tid)
        if not stored:
            return None
        return {"id": stored["id"], "status": stored["status"], **stored["body"]}

    def cancel(self, tid: str) -> bool:
        r = self.t.get(tid)
        if not r or r["status"] != "running":
            return False
        r["task"].cancel()
        r["status"] = "cancelling"
        self._persist(r, "cancelling")
        return True

    def retry(self, tid: str) -> str | None:
        rec = self.get(tid)
        if not rec or rec["status"] not in {"interrupted", "timeout", "cancelled", "failed", "failed_verification"}:
            return None
        new_id = self.start(rec["prompt"], rec.get("mode"), rec.get("tier"), rec.get("max_cost_usd"), rec.get("timeout_s", 300), rec.get("acceptance"))
        self.t[new_id]["retry_of"] = tid
        self._persist(self.t[new_id], "retry")
        return new_id

    def public(self, r) -> dict:
        return {"task_id": r["id"], "status": r["status"], "result": r.get("result"), "error": r.get("error", ""),
                "progress": r.get("progress", 100), "timeout_s": r.get("timeout_s"), "acceptance": r.get("acceptance"),
                "retry_of": r.get("retry_of")}

    def events_since(self, tid: str, after_seq: int) -> list[dict]:
        live_events = self.store.q(
            "SELECT l.seq, l.run_id, l.kind, l.payload FROM ledger l JOIN runs r ON r.id=l.run_id "
            "WHERE r.trigger LIKE ? AND l.seq>? ORDER BY l.seq LIMIT 200", (f"async:{tid}%", after_seq))
        if live_events:
            return live_events
        return [{"seq": event["seq"], "run_id": tid, "kind": event["kind"], "payload": event["body"]}
                for event in self.store.task_events(tid) if event["seq"] > after_seq]
