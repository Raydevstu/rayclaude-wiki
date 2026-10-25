"""Fail-aware debugging attempt ledger for the LAB slice."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DebugAttempt:
    failure: str
    reproduction: str
    evidence: tuple[str, ...]
    hypothesis: str
    changed_files: tuple[str, ...]
    result: str
    regression: bool = False
    decision: str = ""


@dataclass(frozen=True)
class DebugDecision:
    status: str
    reason: str
    decision: str


def evaluate_attempt(attempt: DebugAttempt, previous: tuple[DebugAttempt, ...] = ()) -> DebugDecision:
    """Classify an attempt without applying, reverting, or rerunning any change."""
    if not attempt.failure.strip() or not attempt.reproduction.strip():
        return DebugDecision("BLOCKED", "failure reproduction is incomplete", "escalate")
    if not attempt.evidence:
        return DebugDecision("BLOCKED", "evidence is required before editing", "escalate")
    if not attempt.hypothesis.strip():
        return DebugDecision("BLOCKED", "hypothesis is missing", "escalate")
    if any(item.hypothesis == attempt.hypothesis for item in previous):
        return DebugDecision("BLOCKED", "hypothesis already attempted", "escalate")
    if attempt.regression:
        return DebugDecision("REVIEW", "regression detected", "revert")
    if attempt.result == "fixed":
        return DebugDecision("VERIFIED", "result and regression checks passed", "retain")
    if attempt.result in {"failed", "inconclusive"}:
        return DebugDecision("REVIEW", f"attempt result: {attempt.result}", "supersede")
    return DebugDecision("BLOCKED", "unknown result cannot be accepted", "escalate")
