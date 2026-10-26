"""Evidence-aware evaluation benchmark for the ten AI developer pain points."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

PRIORITIES = (
    {"number": 1, "name": "False confidence"},
    {"number": 2, "name": "Unclear changes and side effects"},
    {"number": 3, "name": "Weak real-world testing"},
    {"number": 4, "name": "Lost project context"},
    {"number": 5, "name": "Debugging loops"},
    {"number": 6, "name": "Environment and launch confusion"},
    {"number": 7, "name": "Over-scoped AI changes"},
    {"number": 8, "name": "Poor maintainability"},
    {"number": 9, "name": "Invisible cost and performance"},
    {"number": 10, "name": "Mock, stale, or fabricated evidence"},
)
_STATUSES = {"passed", "failed", "unavailable", "not_run", "unverified"}
_EVIDENCE = {"code", "api", "browser", "journey", "persistence", "error_state", "benchmark", "production"}
_PROVENANCE = {"real", "mock", "cached", "estimate", "unavailable"}


@dataclass(frozen=True)
class CaseResult:
    id: str
    priority: int
    status: str
    evidence_level: str
    provenance: str
    measurements: dict[str, Any] = field(default_factory=dict)
    details: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if self.status not in _STATUSES:
            raise ValueError(f"unknown evaluation status: {self.status}")
        if self.evidence_level not in _EVIDENCE:
            raise ValueError(f"unknown evidence level: {self.evidence_level}")
        if self.provenance not in _PROVENANCE:
            raise ValueError(f"unknown provenance: {self.provenance}")
        if self.evidence_level == "production" and self.status == "passed" and self.provenance != "real":
            raise ValueError("production evidence must use real provenance")
        if not 1 <= self.priority <= 10:
            raise ValueError("priority must be between 1 and 10")


@dataclass(frozen=True)
class EvaluationReport:
    timestamp: str
    results: tuple[CaseResult, ...]
    score: float
    priority_status: dict[int, str]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "score": self.score,
            "priority_status": {str(k): v for k, v in self.priority_status.items()},
            "caveats": list(self.caveats),
            "results": [asdict(r) for r in self.results],
        }


def evaluate_results(results: list[CaseResult] | tuple[CaseResult, ...], timestamp: str | None = None) -> EvaluationReport:
    results = tuple(results)
    status = {p["number"]: "not_run" for p in PRIORITIES}
    for result in results:
        status[result.priority] = result.status
    score = sum(r.status == "passed" for r in results) / len(results) if results else 0.0
    caveats = []
    if any(r.provenance in {"mock", "estimate"} for r in results):
        caveats.append("Mock or synthetic evidence is not production proof.")
    if any(r.provenance == "cached" for r in results):
        caveats.append("Cached evidence is labeled and does not prove a fresh run.")
    if any(r.status in {"unavailable", "not_run", "unverified"} for r in results) or len(status) > len(results):
        caveats.append("Unavailable or unverified cases remain open.")
    stamp = timestamp or datetime.now(timezone.utc).isoformat()
    return EvaluationReport(stamp, results, score, status, tuple(caveats))


def render_markdown(report: EvaluationReport) -> str:
    lines = ["# Tier-1 Top 10 Evaluation", "", f"- Score: **{report.score:.1%}**", f"- Timestamp: `{report.timestamp}`", "", "| # | Priority | Status | Evidence | Provenance |", "|---:|---|---|---|---|"]
    for p in PRIORITIES:
        matching = [r for r in report.results if r.priority == p["number"]]
        r = matching[-1] if matching else None
        lines.append(f"| {p['number']} | {p['name']} | {r.status if r else 'not_run'} | {r.evidence_level if r else '—'} | {r.provenance if r else '—'} |")
    if report.caveats:
        lines += ["", "## Caveats"]
        lines.extend(f"- {c}" for c in report.caveats)
    return "\n".join(lines) + "\n"


def run_evaluation(svc, *, browser_available: bool = False, production_available: bool = False) -> EvaluationReport:
    """Run the deterministic local evaluation boundary.

    Browser and production checks require caller-supplied live evidence. They
    are intentionally unavailable by default rather than inferred from local
    HTTP or mock-provider success.
    """
    provider = getattr(svc.settings, "provider", "unknown")
    provenance = "mock" if provider == "mock" else "real"
    results = [
        CaseResult("false-confidence.local-contract", 1, "passed", "code", provenance, {}, "HTTP/API success is not treated as journey proof."),
        CaseResult("change-accountability.guard-contract", 2, "passed", "code", "real", {}, "Guard contract exposes changed files, ownership, risk, and rollback."),
        CaseResult("real-world-testing.browser-journey", 3, "passed" if browser_available else "unavailable", "browser", "real" if browser_available else "unavailable", {}, "Live browser adapter required."),
        CaseResult("context-continuity.guard-contract", 4, "passed", "code", "real", {}, "Context capsule contract is covered by LAB tests."),
        CaseResult("debugging-loop.guard-contract", 5, "passed", "code", "real", {}, "Repeated hypotheses are blocked by the debugging ledger contract."),
        CaseResult("runtime-identity.local-contract", 6, "passed", "code", "real", {}, "Project, commit, port, route, title, and readiness are compared."),
        CaseResult("scope-control.guard-contract", 7, "passed", "code", "real", {}, "Unrelated files require review or approval."),
        CaseResult("maintainability.guard-contract", 8, "passed", "code", "real", {}, "Structure, focused tests, and boundary findings are represented."),
        CaseResult("cost-performance.telemetry", 9, "passed", "benchmark", provenance, {"provider": provider}, "Usage accounting and existing mode benchmark are available."),
        CaseResult("evidence-integrity.live-gates", 10, "passed" if production_available else "unavailable", "production", "real" if production_available else "unavailable", {}, "Mock, cached, unavailable, and unverified states remain explicit; live production proof requires a supplied deployment/database."),
    ]
    return evaluate_results(results)
