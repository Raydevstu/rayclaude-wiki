"""Benchmark execution modes on your own tasks: cost, calls, latency, verification outcome.

The cache is cleared before every measured run so no mode benefits from another mode's cached answers.
With the mock provider the numbers only exercise the plumbing; run it against a real provider to learn anything.
"""
from __future__ import annotations
import asyncio, time

BENCH_MODES = ("autopilot", "ralph", "team")


def _load(tasks) -> list[dict]:
    out = []
    for task in tasks:
        if isinstance(task, str):
            prompt, expect = task, []
        else:
            task = task or {}
            prompt, expect = task.get("prompt", ""), task.get("expect", [])
        if isinstance(prompt, str) and prompt.strip():
            out.append({"prompt": prompt.strip(), "expect": [str(x) for x in expect] if isinstance(expect, list) else []})
    if not 1 <= len(out) <= 25:
        raise ValueError("provide 1-25 task prompts")
    return out


async def run_bench(svc, tasks, modes=BENCH_MODES, max_cost_usd: float | None = None, timeout_s: float = 120) -> dict:
    prompts = _load(tasks)
    bad = [m for m in modes if m not in BENCH_MODES]
    if bad:
        raise ValueError(f"unknown modes {bad}; choose from {BENCH_MODES}")
    rows = []
    for task in prompts:
        p, expected = task["prompt"], task["expect"]
        for m in modes:
            svc.store.x("DELETE FROM cache")
            t0 = time.perf_counter()
            try:
                r = await asyncio.wait_for(svc.modes.run(p, mode=m, trigger="bench", max_cost_usd=max_cost_usd), timeout=timeout_s)
                answer = str(r.get("answer", ""))
                correctness = "passed" if all(token.lower() in answer.lower() for token in expected) else ("unverified" if not expected else "failed")
                rows.append({"prompt": p[:80], "mode": m, "status": r["status"], "calls": r["usage"]["calls"],
                             "cost_usd": r["usage"]["cost_usd"], "audit": (r.get("audit") or {}).get("score"),
                             "iterations": r.get("iterations", 1), "latency_s": round(time.perf_counter() - t0, 2),
                             "run_id": r["run_id"], "correctness": correctness})
            except asyncio.TimeoutError:
                rows.append({"prompt": p[:80], "mode": m, "status": "timeout", "error": f"exceeded {timeout_s:.1f}s",
                             "calls": 0, "cost_usd": 0.0, "audit": None, "iterations": 0, "latency_s": round(time.perf_counter() - t0, 2),
                             "run_id": "", "correctness": "unverified"})
            except Exception as e:
                rows.append({"prompt": p[:80], "mode": m, "status": "error", "error": f"{type(e).__name__}: {e}"[:160],
                             "calls": 0, "cost_usd": 0.0, "audit": None, "iterations": 0, "latency_s": 0.0,
                             "run_id": "", "correctness": "unverified"})
    summary = {}
    for m in modes:
        rs = [r for r in rows if r["mode"] == m]
        sc = [r["audit"] for r in rs if r["audit"] is not None]
        ok = sum(1 for r in rs if r["status"] == "ok")
        correct = [r for r in rs if r["correctness"] != "unverified"]
        summary[m] = {"runs": len(rs), "ok_rate": round(ok / len(rs), 3), "avg_cost_usd": round(sum(r["cost_usd"] for r in rs) / len(rs), 6),
                      "avg_calls": round(sum(r["calls"] for r in rs) / len(rs), 2),
                      "avg_audit": round(sum(sc) / len(sc), 3) if sc else None,
                      "cost_per_ok_usd": round(sum(r["cost_usd"] for r in rs) / ok, 6) if ok else None,
                      "correctness_rate": round(sum(r["correctness"] == "passed" for r in correct) / len(correct), 3) if correct else None}
    return {"provider": svc.settings.provider, "tasks": len(prompts), "rows": rows, "summary": summary,
            "caveat": ("mock provider: costs and scores are synthetic" if svc.settings.provider == "mock" else
                       "audit scores come from the pipeline's own auditor, not an independent judge")}
