"""Read-only runtime identity and launch consistency guard."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeContract:
    project: str
    commit: str
    port: int
    route: str
    title: str


@dataclass(frozen=True)
class RuntimeEvidence:
    project: str
    commit: str
    port: int
    route: str
    title: str
    http_status: int | None = None
    ready: bool = False


@dataclass(frozen=True)
class RuntimeDecision:
    status: str
    mismatches: tuple[str, ...]
    recommendation: str


def inspect_runtime(expected: RuntimeContract, observed: RuntimeEvidence) -> RuntimeDecision:
    """Compare expected and observed identity without changing runtime state."""
    mismatches: list[str] = []
    checks = (
        (expected.project == observed.project, "wrong project"),
        (expected.commit == observed.commit, "stale or wrong commit"),
        (expected.port == observed.port, "wrong port"),
        (expected.route == observed.route, "wrong route"),
        (expected.title == observed.title, "wrong page title"),
        (observed.http_status == 200, "HTTP 200 not verified"),
        (observed.ready, "runtime not ready"),
    )
    mismatches.extend(label for passed, label in checks if not passed)
    if not mismatches:
        return RuntimeDecision("READY", (), "safe to continue with the verified runtime")
    if "wrong project" in mismatches or "wrong port" in mismatches or "wrong page title" in mismatches:
        recommendation = "do not edit application files; launch or inspect the intended application"
    else:
        recommendation = "inspect the reported runtime mismatch before making changes"
    return RuntimeDecision("UNVERIFIED", tuple(mismatches), recommendation)
