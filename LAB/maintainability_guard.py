"""Objective maintainability checks for the LAB slice."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MaintainabilityInput:
    patterns_reused: bool
    unnecessary_abstraction: bool = False
    duplication: bool = False
    boundary_violation: bool = False
    focused_tests: bool = False
    complexity: bool = False
    decision_record_needed: bool = False
    dependency_concern: bool = False
    findings: tuple[str, ...] = ()


@dataclass(frozen=True)
class MaintainabilityReport:
    status: str
    findings: tuple[str, ...]
    recommendation: str


def evaluate_maintainability(observed: MaintainabilityInput) -> MaintainabilityReport:
    """Return a reviewable result without making subjective code changes."""
    findings = list(observed.findings)
    checks = (
        (not observed.patterns_reused, "existing project pattern not reused"),
        (observed.unnecessary_abstraction, "unnecessary abstraction"),
        (observed.duplication, "duplication detected"),
        (observed.boundary_violation, "module boundary violation"),
        (not observed.focused_tests, "focused tests missing"),
        (observed.complexity, "complexity requires review"),
        (observed.dependency_concern, "dependency concern"),
        (observed.decision_record_needed, "architectural decision record required"),
    )
    findings.extend(label for failed, label in checks if failed)
    status = "BLOCKED" if observed.boundary_violation else "REVIEW" if findings else "CLEAR"
    recommendation = "review findings before acceptance" if findings else "safe to accept maintainability evidence"
    return MaintainabilityReport(status, tuple(dict.fromkeys(findings)), recommendation)
