from __future__ import annotations
import json, sqlite3, threading, time
from datetime import datetime, timezone
from pathlib import Path

from .util import rank, sha

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY, ts REAL, day TEXT, run_id TEXT, task TEXT, tier TEXT,
  model TEXT, in_tok INT, out_tok INT, cost REAL, ms INT);
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, ts REAL, trigger TEXT, prompt TEXT, status TEXT, result TEXT,
  baseline_cost REAL DEFAULT 0, actual_cost REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS ledger(seq INTEGER PRIMARY KEY, ts TEXT, run_id TEXT, kind TEXT, payload TEXT, prev TEXT, hash TEXT);
CREATE TABLE IF NOT EXISTS capsules(run_id TEXT PRIMARY KEY, body TEXT);
CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, val TEXT, exp REAL);
CREATE TABLE IF NOT EXISTS memory(id INTEGER PRIMARY KEY, ts REAL, text TEXT, tags TEXT);
CREATE TABLE IF NOT EXISTS jobs(name TEXT PRIMARY KEY, kind TEXT, spec TEXT, prompt TEXT, enabled INT,
  last_minute TEXT, last_run TEXT, last_status TEXT);
CREATE TABLE IF NOT EXISTS approval_records(id TEXT PRIMARY KEY, ts REAL, status TEXT, body TEXT);
CREATE TABLE IF NOT EXISTS guard_write_audits(id TEXT PRIMARY KEY, approval_id TEXT, ts REAL,
  action TEXT, status TEXT, body TEXT);
"""
GENESIS = "0" * 64


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class Store:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            if path != ":memory:":
                self.db.execute("PRAGMA journal_mode=WAL")
            self.db.executescript(SCHEMA)

    def x(self, sql: str, args=()):
        with self.lock:
            return self.db.execute(sql, args)

    def q(self, sql: str, args=()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    # ---- usage telemetry
    def usage_add(self, run_id, task, tier, model, i, o, cost, ms):
        self.x("INSERT INTO usage(ts,day,run_id,task,tier,model,in_tok,out_tok,cost,ms) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (time.time(), _today(), run_id, task, tier, model, i, o, cost, ms))

    def spend_today(self) -> float:
        return self.q("SELECT COALESCE(SUM(cost),0) c FROM usage WHERE day=?", (_today(),))[0]["c"]

    def run_usage(self, run_id: str) -> dict:
        r = self.q("SELECT COUNT(*) calls, COALESCE(SUM(in_tok),0) i, COALESCE(SUM(out_tok),0) o, "
                   "COALESCE(SUM(cost),0) cost FROM usage WHERE run_id=?", (run_id,))[0]
        return {"calls": r["calls"], "input_tokens": r["i"], "output_tokens": r["o"], "cost_usd": r["cost"]}

    def usage_summary(self) -> dict:
        by_tier = self.q("SELECT tier, COUNT(*) calls, SUM(in_tok) in_tok, SUM(out_tok) out_tok, SUM(cost) cost "
                         "FROM usage GROUP BY tier")
        by_task = self.q("SELECT task, COUNT(*) calls, SUM(in_tok) in_tok, SUM(out_tok) out_tok, SUM(cost) cost "
                         "FROM usage GROUP BY task")
        daily = self.q("SELECT day, SUM(cost) cost, SUM(in_tok+out_tok) tokens FROM usage GROUP BY day "
                       "ORDER BY day DESC LIMIT 14")
        sv = self.q("SELECT COUNT(*) runs, COALESCE(SUM(baseline_cost),0) b, COALESCE(SUM(actual_cost),0) a "
                    "FROM runs WHERE status='ok' AND baseline_cost>0")[0]
        saved = round((1 - sv["a"] / sv["b"]) * 100, 1) if sv["b"] else None
        return {"by_tier": by_tier, "by_task": by_task, "daily": daily, "spend_today_usd": self.spend_today(),
                "measured_runs": sv["runs"], "baseline_cost_usd": sv["b"], "actual_cost_usd": sv["a"],
                "saved_pct": saved}

    # ---- runs
    def run_start(self, run_id, prompt, trigger):
        self.x("INSERT OR REPLACE INTO runs(id,ts,trigger,prompt,status,result) VALUES(?,?,?,?,?,?)",
               (run_id, time.time(), trigger, prompt[:4000], "running", ""))

    def run_finish(self, run_id, status, result: dict, baseline=0.0, actual=0.0):
        self.x("UPDATE runs SET status=?, result=?, baseline_cost=?, actual_cost=? WHERE id=?",
               (status, json.dumps(result, default=str), baseline, actual, run_id))

    def run_get(self, run_id):
        r = self.q("SELECT * FROM runs WHERE id=?", (run_id,))
        if not r:
            return None
        r = r[0]
        r["result"] = json.loads(r["result"]) if r["result"] else None
        return r

    def runs_list(self, limit=50):
        return self.q("SELECT id, ts, trigger, substr(prompt,1,120) prompt, status, baseline_cost, actual_cost "
                      "FROM runs ORDER BY ts DESC LIMIT ?", (limit,))

    # ---- evidence ledger (hash chain)
    def ledger_append(self, run_id: str, kind: str, payload: dict) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                row = self.db.execute("SELECT seq, hash FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
                prev = row["hash"] if row else GENESIS
                seq = (row["seq"] + 1) if row else 1
                ts = f"{time.time():.6f}"
                h = sha(f"{seq}|{ts}|{run_id}|{kind}|{body}|{prev}")
                self.db.execute("INSERT INTO ledger(seq,ts,run_id,kind,payload,prev,hash) VALUES(?,?,?,?,?,?,?)",
                                (seq, ts, run_id, kind, body, prev, h))
                self.db.execute("COMMIT")
                return h
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def ledger_list(self, run_id=None, limit=200):
        if run_id:
            return self.q("SELECT * FROM ledger WHERE run_id=? ORDER BY seq LIMIT ?", (run_id, limit))
        return self.q("SELECT * FROM ledger ORDER BY seq DESC LIMIT ?", (limit,))

    def ledger_verify(self) -> dict:
        prev, n = GENESIS, 0
        for r in self.q("SELECT * FROM ledger ORDER BY seq"):
            exp = sha(f"{r['seq']}|{r['ts']}|{r['run_id']}|{r['kind']}|{r['payload']}|{prev}")
            if r["prev"] != prev or r["hash"] != exp or r["seq"] != n + 1:
                return {"ok": False, "entries": n, "broken_at": r["seq"]}
            prev, n = r["hash"], n + 1
        return {"ok": True, "entries": n, "head": prev}

    # ---- capsules, cache, memory
    def capsule_put(self, run_id, body: dict):
        self.x("INSERT OR REPLACE INTO capsules(run_id,body) VALUES(?,?)", (run_id, json.dumps(body, default=str)))

    def capsule_get(self, run_id):
        r = self.q("SELECT body FROM capsules WHERE run_id=?", (run_id,))
        return json.loads(r[0]["body"]) if r else None

    def cache_get(self, key):
        r = self.q("SELECT val FROM cache WHERE key=? AND exp>?", (key, time.time()))
        return r[0]["val"] if r else None

    def cache_put(self, key, val, ttl):
        self.x("INSERT OR REPLACE INTO cache(key,val,exp) VALUES(?,?,?)", (key, val, time.time() + ttl))
        self.x("DELETE FROM cache WHERE exp<?", (time.time(),))

    def memory_add(self, text, tags=""):
        self.x("INSERT INTO memory(ts,text,tags) VALUES(?,?,?)", (time.time(), text[:4000], tags))
        self.x("DELETE FROM memory WHERE id NOT IN (SELECT id FROM memory ORDER BY id DESC LIMIT 2000)")

    def memory_search(self, query, k=3):
        rows = self.q("SELECT id, text FROM memory ORDER BY id DESC LIMIT 500")
        return [rows[i]["text"] for i, _ in rank(query, [r["text"] for r in rows], k)]

    def memory_list(self, limit=50):
        return self.q("SELECT id, ts, substr(text,1,200) text, tags FROM memory ORDER BY id DESC LIMIT ?", (limit,))

    # ---- guarded write approvals
    def approval_put(self, record_id: str, status: str, body: dict):
        self.x("INSERT OR REPLACE INTO approval_records(id,ts,status,body) VALUES(?,?,?,?)",
               (record_id, time.time(), status, json.dumps(body, default=str)))

    def approval_get(self, record_id: str):
        rows = self.q("SELECT id, ts, status, body FROM approval_records WHERE id=?", (record_id,))
        if not rows:
            return None
        row = rows[0]
        row["body"] = json.loads(row["body"])
        return row

    def approvals_list(self, limit=50):
        return self.q("SELECT id, ts, status FROM approval_records ORDER BY ts DESC LIMIT ?", (limit,))

    # ---- guarded write execution audit
    def write_audit_put(self, audit_id: str, approval_id: str, action: str, status: str, body: dict):
        self.x("INSERT OR REPLACE INTO guard_write_audits(id,approval_id,ts,action,status,body) VALUES(?,?,?,?,?,?)",
               (audit_id, approval_id, time.time(), action, status, json.dumps(body, default=str)))

    def write_audit_get(self, audit_id: str):
        rows = self.q("SELECT id, approval_id, ts, action, status, body FROM guard_write_audits WHERE id=?", (audit_id,))
        if not rows:
            return None
        row = rows[0]
        row["body"] = json.loads(row["body"])
        return row

    def write_audits_list(self, approval_id: str, limit=20):
        rows = self.q("SELECT id, approval_id, ts, action, status, body FROM guard_write_audits WHERE approval_id=? ORDER BY ts DESC LIMIT ?",
                      (approval_id, limit))
        for row in rows:
            row["body"] = json.loads(row["body"])
        return rows

    # ---- jobs
    def job_put(self, name, kind, spec, prompt, enabled=True):
        self.x("INSERT OR REPLACE INTO jobs(name,kind,spec,prompt,enabled) VALUES(?,?,?,?,?)",
               (name, kind, spec, prompt, int(enabled)))

    def job_get(self, name):
        r = self.q("SELECT * FROM jobs WHERE name=?", (name,))
        return r[0] if r else None

    def jobs_list(self):
        return self.q("SELECT * FROM jobs ORDER BY name")

    def job_delete(self, name):
        return self.x("DELETE FROM jobs WHERE name=?", (name,)).rowcount > 0

    def job_mark(self, name, **kw):
        for k, v in kw.items():
            if k in ("last_minute", "last_run", "last_status"):
                self.x(f"UPDATE jobs SET {k}=? WHERE name=?", (v, name))
