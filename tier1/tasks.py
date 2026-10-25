"""Background runs: start, poll, stream progress (from the evidence ledger) and cancel."""
from __future__ import annotations
import asyncio, time, uuid

MAX_ACTIVE, KEEP = 20, 200


class TaskLimit(Exception):
    pass


class Tasks:
    def __init__(self, modes, store):
        self.modes, self.store, self.t = modes, store, {}

    def start(self, prompt: str, mode=None, tier=None, max_cost_usd=None) -> str:
        if sum(1 for x in self.t.values() if x["status"] == "running") >= MAX_ACTIVE:
            raise TaskLimit("too many active tasks")
        tid = uuid.uuid4().hex[:12]
        rec = {"id": tid, "status": "running", "ts": time.time(), "result": None, "error": ""}
        rec["task"] = asyncio.create_task(self._go(rec, prompt, mode, tier, max_cost_usd))
        self.t[tid] = rec
        for k in sorted(self.t, key=lambda k: self.t[k]["ts"])[:-KEEP]:       # bounded memory
            if self.t[k]["status"] != "running":
                del self.t[k]
        return tid

    async def _go(self, rec, prompt, mode, tier, max_cost_usd=None):
        try:
            rec["result"] = await self.modes.run(prompt, mode=mode, tier=tier, trigger=f"async:{rec['id']}",
                                                max_cost_usd=max_cost_usd)
            rec["status"] = "done"
        except asyncio.CancelledError:
            rec["status"] = "cancelled"
            self._close_runs(rec["id"], "cancelled")
        except Exception as e:
            rec["status"], rec["error"] = "failed", f"{type(e).__name__}: {e}"[:300]

    def _close_runs(self, tid: str, status: str):
        for r in self.store.q("SELECT id FROM runs WHERE trigger LIKE ? AND status='running'", (f"async:{tid}%",)):
            self.store.ledger_append(r["id"], f"run_{status}", {})
            self.store.run_finish(r["id"], status, {"status": status})

    def get(self, tid: str):
        return self.t.get(tid)

    def cancel(self, tid: str) -> bool:
        r = self.t.get(tid)
        if not r or r["status"] != "running":
            return False
        r["task"].cancel()
        return True

    def public(self, r) -> dict:
        return {"task_id": r["id"], "status": r["status"], "result": r["result"], "error": r["error"]}

    def events_since(self, tid: str, after_seq: int) -> list[dict]:
        return self.store.q(
            "SELECT l.seq, l.run_id, l.kind, l.payload FROM ledger l JOIN runs r ON r.id=l.run_id "
            "WHERE r.trigger LIKE ? AND l.seq>? ORDER BY l.seq LIMIT 200", (f"async:{tid}%", after_seq))
