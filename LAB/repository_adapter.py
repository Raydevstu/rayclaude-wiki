"""Read-only repository identity for the guard boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class RepositoryIdentity:
    root: str
    is_git: bool
    branch: str
    commit: str
    dirty: bool


def repository_mismatch(identity: RepositoryIdentity, expected_branch: str | None = None,
                        expected_commit: str | None = None) -> str | None:
    """Return the first identity mismatch that makes a write unsafe."""
    if not identity.is_git:
        return "repository is not a Git worktree"
    if expected_branch and identity.branch != expected_branch:
        return f"branch mismatch: expected {expected_branch}, observed {identity.branch}"
    if expected_commit and identity.commit != expected_commit:
        return f"commit mismatch: expected {expected_commit}, observed {identity.commit}"
    return None


def _git(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(["git", "-C", str(root), *args], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def inspect_repository(path: str | Path) -> RepositoryIdentity:
    root = Path(path).resolve()
    if not root.is_dir():
        raise ValueError(f"repository path is not a directory: {root}")
    branch = _git(root, "branch", "--show-current")
    commit = _git(root, "rev-parse", "--short", "HEAD")
    status = _git(root, "status", "--porcelain")
    is_git = branch is not None or commit is not None or status is not None
    return RepositoryIdentity(str(root), is_git, branch or "unavailable", commit or "unavailable",
                              bool(status))
