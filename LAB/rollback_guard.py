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


def plan_rollback(files: tuple[FileOwnership, ...], *, confirmed_irreversible: bool = False) -> RollbackPlan:
    """Return a plan without changing files or claiming that rollback was executed."""
    user = tuple(item.path for item in files if item.owner == "user")
    ai = tuple(item.path for item in files if item.owner == "ai")
    irreversible = tuple(item.path for item in files if not item.reversible or item.owner == "external")
    if irreversible and not confirmed_irreversible:
        return RollbackPlan("BLOCKED", ai, user, ai, irreversible,
                            ("obtain explicit approval for irreversible or external effects",))
    return RollbackPlan("READY", ai, user, ai, irreversible,
                        tuple(f"restore AI-owned baseline for {path}" for path in ai))
