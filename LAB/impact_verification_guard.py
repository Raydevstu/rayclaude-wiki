"""Dependency-free impact and evidence guards for the LAB slice."""

from __future__ import annotations

from dataclasses import dataclass

from scope_guard import ChangedFile, ScopeResult


@dataclass(frozen=True)
class ImpactReport:
    changed_files: tuple[str, ...]
    reasons: tuple[str, ...]
    affected_layers: tuple[str, ...]
    risks: tuple[str, ...]
    rollback: str
    status: str

    def to_dict(self) -> dict:
        return {key: list(value) if isinstance(value, tuple) else value
                for key, value in self.__dict__.items()}


def explain_impact(changes: list[ChangedFile], scope: ScopeResult) -> ImpactReport:
    """Turn observed changes and scope findings into an auditable explanation."""
    layers = tuple(sorted({change.layer for change in changes if change.layer}))
    risks = list(scope.violations) + list(scope.warnings)
    for change in changes:
        if change.destructive:
            risks.append(f"irreversible or destructive operation: {change.path}")
    reasons = tuple(
        f"{change.path}: {change.changed_lines} changed lines in {change.layer or 'unknown'} layer"
        for change in changes
    )
    return ImpactReport(
        changed_files=tuple(change.path for change in changes),
        reasons=reasons,
        affected_layers=layers,
        risks=tuple(dict.fromkeys(risks)),
        rollback="unavailable" if not scope.rollback_available else "available for observed file changes",
        status="REVIEW" if risks else "CLEAR",
    )


@dataclass(frozen=True)
class VerificationEvidence:
    expected_project: str
    observed_project: str
    expected_route: str
    observed_route: str
    http_status: int | None
    page_title: str
    assets_loaded: bool
    browser_rendered: bool
    acceptance_passed: bool


@dataclass(frozen=True)
class VerificationResult:
    status: str
    failures: tuple[str, ...]


def verify(evidence: VerificationEvidence) -> VerificationResult:
    """Require identity, route, assets, rendering, and acceptance evidence."""
    failures: list[str] = []
    checks = (
        (evidence.expected_project == evidence.observed_project, "project identity mismatch"),
        (evidence.expected_route == evidence.observed_route, "route mismatch"),
        (evidence.http_status == 200, "HTTP 200 evidence missing"),
        (bool(evidence.page_title.strip()), "page title missing"),
        (evidence.assets_loaded, "assets not verified"),
        (evidence.browser_rendered, "browser rendering not verified"),
        (evidence.acceptance_passed, "acceptance criteria not verified"),
    )
    failures.extend(message for passed, message in checks if not passed)
    return VerificationResult("VERIFIED" if not failures else "UNVERIFIED", tuple(failures))
