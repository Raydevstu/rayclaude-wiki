"""Deterministic benchmark for the integrated guard decision pipeline."""

from __future__ import annotations

from time import perf_counter

from cost_performance_guard import CallRecord, summarize_calls
from guard_orchestrator import BrowserRepairInput, run_browser_repair


def benchmark(cases: tuple[BrowserRepairInput, ...]) -> dict:
    started = perf_counter()
    results = tuple(run_browser_repair(case) for case in cases)
    elapsed = round((perf_counter() - started) * 1000, 3)
    verified = sum(result.status == "VERIFIED" for result in results)
    blocked = len(results) - verified
    false_successes = sum(result.status == "VERIFIED" and result.evidence_status != "VERIFIED" for result in results)
    scope_blocks = sum(result.stopped_at == "scope" for result in results)
    telemetry = summarize_calls((CallRecord(0, 0, "none", "local", 0.0, int(elapsed)),))
    return {
        "cases": len(results), "verified": verified, "blocked": blocked,
        "task_success_rate": verified / len(results) if results else 0.0,
        "false_success_rate": false_successes / len(results) if results else 0.0,
        "scope_violations": scope_blocks, "latency_ms": elapsed,
        "retries": telemetry.retries, "tool_calls": telemetry.tool_calls,
        "input_tokens": telemetry.input_tokens, "output_tokens": telemetry.output_tokens,
        "cost": telemetry.cost, "evidence_completeness": verified / len(results) if results else 0.0,
        "user_intervention": sum(result.status == "BLOCKED" for result in results),
    }
