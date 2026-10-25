"""Fail-closed task capsule validation for context continuity."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskCapsuleInput:
    project: str
    canonical_sources: tuple[str, ...]
    freshness: str
    goal: str
    implementation_state: str
    constraints: tuple[str, ...]
    relevant_files: tuple[str, ...]
    decisions: tuple[str, ...]
    verification: tuple[str, ...]
    next_boundary: str
    risks: tuple[str, ...] = ()
    repository_root: str = ""
    repository_branch: str = "unavailable"
    repository_commit: str = "unavailable"
    repository_dirty: bool | None = None


@dataclass(frozen=True)
class TaskCapsule:
    project: str
    goal: str
    implementation_state: str
    constraints: tuple[str, ...]
    relevant_files: tuple[str, ...]
    decisions: tuple[str, ...]
    verification: tuple[str, ...]
    next_boundary: str
    risks: tuple[str, ...]
    version: int = 1
    repository_root: str = ""
    repository_branch: str = "unavailable"
    repository_commit: str = "unavailable"
    repository_dirty: bool | None = None


@dataclass(frozen=True)
class CapsuleDecision:
    status: str
    reasons: tuple[str, ...]


def validate_capsule(data: TaskCapsuleInput) -> tuple[TaskCapsule | None, CapsuleDecision]:
    """Return READY only when continuation-critical context is complete and current."""
    missing = []
    for value, label in ((data.project, "project identity"), (data.goal, "goal"),
                         (data.implementation_state, "implementation state"),
                         (data.next_boundary, "next boundary")):
        if not value.strip():
            missing.append(label)
    reasons = list(missing)
    if not data.canonical_sources:
        reasons.append("canonical source")
    if len(data.canonical_sources) > 1:
        reasons.append("conflicting canonical sources")
    if data.freshness != "current":
        reasons.append(f"context is {data.freshness}")
    if not data.verification:
        reasons.append("verification evidence")
    if reasons:
        return None, CapsuleDecision("BLOCKED", tuple(reasons))
    capsule = TaskCapsule(data.project, data.goal.strip(), data.implementation_state.strip(),
                          data.constraints, data.relevant_files, data.decisions,
                          data.verification, data.next_boundary.strip(), data.risks,
                          repository_root=data.repository_root,
                          repository_branch=data.repository_branch,
                          repository_commit=data.repository_commit,
                          repository_dirty=data.repository_dirty)
    return capsule, CapsuleDecision("READY", ())
