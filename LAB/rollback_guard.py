"""Ownership-aware rollback planning for guarded write actions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileOwnership:
    path: str
    baseline_digest: str
    current_digest: str
    owner: str
    reversible: bool = True


@dataclass(frozen=True)
class RollbackPlan:
    status: str
    boundary: tuple[str, ...]
    protected_user_files: tuple[str, ...]
    ai_files: tuple[str, ...]
    irreversible: tuple[str, ...]
    instructions: tuple[str, ...]
    baseline_digests: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class OwnershipConfirmation:
    """Explicit authority for a guarded write; this does not execute the write."""
    repository_commit: str
    repository_branch: str
    ai_files: tuple[str, ...]
    protected_user_files: tuple[str, ...] = ()


def ownership_mismatch(plan: RollbackPlan, confirmation: OwnershipConfirmation | None,
                       *, repository_commit: str, repository_branch: str) -> str | None:
    if confirmation is None:
        return "explicit ownership confirmation is required before writing"
    if confirmation.repository_commit != repository_commit:
        return "ownership confirmation commit does not match the inspected repository"
    if confirmation.repository_branch != repository_branch:
        return "ownership confirmation branch does not match the inspected repository"
    if set(confirmation.ai_files) != set(plan.ai_files):
        return "ownership confirmation does not exactly match AI-owned rollback files"
    if set(confirmation.protected_user_files) != set(plan.protected_user_files):
        return "ownership confirmation does not exactly match protected user files"
    return None


def plan_rollback(files: tuple[FileOwnership, ...], *, confirmed_irreversible: bool = False) -> RollbackPlan:
    """Return a plan without changing files or claiming that rollback was executed."""
    user = tuple(item.path for item in files if item.owner == "user")
    ai = tuple(item.path for item in files if item.owner == "ai")
    irreversible = tuple(item.path for item in files if not item.reversible or item.owner == "external")
    if irreversible and not confirmed_irreversible:
        return RollbackPlan("BLOCKED", ai, user, ai, irreversible,
                            ("obtain explicit approval for irreversible or external effects",),
                            tuple((item.path, item.baseline_digest) for item in files))
    return RollbackPlan("READY", ai, user, ai, irreversible,
                        tuple(f"restore AI-owned baseline for {path}" for path in ai),
                        tuple((item.path, item.baseline_digest) for item in files))
