"""Evidence-backed post-change accountability for the LAB slice."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChangeAccountabilityContract:
    request: str
    allowed_files: tuple[str, ...]


@dataclass(frozen=True)
class ObservedImpact:
    path: str
    functions: tuple[str, ...] = ()
    behavior: str = ""
    pre_existing: bool = False
    generated: bool = False
    dependencies: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    provenance: str = "observed"
    rollback: str = "available"


@dataclass(frozen=True)
class AccountabilityReport:
    status: str
    changed_files: tuple[str, ...]
    unexplained_files: tuple[str, ...]
    behaviors: tuple[str, ...]
    dependencies: tuple[str, ...]
    risks: tuple[str, ...]
    tests: tuple[str, ...]
    provenance: tuple[str, ...]
    rollback: tuple[str, ...]


def audit_changes(contract: ChangeAccountabilityContract, impacts: tuple[ObservedImpact, ...]) -> AccountabilityReport:
    """Audit observed impacts without claiming unknown effects are safe."""
    changed = tuple(item.path for item in impacts)
    unexplained = tuple(path for path in changed if path not in contract.allowed_files)
    behaviors = tuple(item.behavior for item in impacts if item.behavior)
    dependencies = tuple(dict.fromkeys(dep for item in impacts for dep in item.dependencies))
    risks = list(dict.fromkeys(risk for item in impacts for risk in item.risks))
    if unexplained:
        risks.append("unexplained file outside approved boundary")
    tests = tuple(dict.fromkeys(test for item in impacts for test in item.tests))
    provenance = tuple(sorted({item.provenance for item in impacts}))
    rollback = tuple(f"{item.path}: {item.rollback}" for item in impacts)
    status = "REVIEW" if unexplained or risks or any(item.generated for item in impacts) else "CLEAR"
    return AccountabilityReport(status, changed, unexplained, behaviors, dependencies,
                                tuple(dict.fromkeys(risks)), tests, provenance, rollback)
