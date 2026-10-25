"""Token, cost, latency, retry, cache, and tool-call accounting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CallRecord:
    input_tokens: int
    output_tokens: int
    model: str
    provider: str
    cost: float | None
    latency_ms: int
    retries: int = 0
    failed: bool = False
    cache_hit: bool = False
    tool_calls: int = 0


@dataclass(frozen=True)
class CostPerformanceReport:
    input_tokens: int
    output_tokens: int
    models: tuple[str, ...]
    providers: tuple[str, ...]
    cost: float | None
    latency_ms: int
    retries: int
    failed_calls: int
    cache_hits: int
    tool_calls: int
    cost_status: str


def summarize_calls(records: tuple[CallRecord, ...]) -> CostPerformanceReport:
    """Aggregate supplied call telemetry without turning unknown cost into zero."""
    known_costs = [record.cost for record in records if record.cost is not None]
    return CostPerformanceReport(
        sum(record.input_tokens for record in records),
        sum(record.output_tokens for record in records),
        tuple(sorted({record.model for record in records})),
        tuple(sorted({record.provider for record in records})),
        sum(known_costs) if len(known_costs) == len(records) else None,
        sum(record.latency_ms for record in records),
        sum(record.retries for record in records),
        sum(record.failed for record in records),
        sum(record.cache_hit for record in records),
        sum(record.tool_calls for record in records),
        "actual" if len(known_costs) == len(records) else "unavailable",
    )
