"""Fail-closed Context Continuity Guard LAB slice."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextSource:
    name: str
    project: str
    authority: str
    freshness: str
    facts: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextCapsule:
    project: str
    authoritative_sources: tuple[str, ...]
    facts: tuple[str, ...]
    next_boundary: str


@dataclass(frozen=True)
class ContextIntegrityReport:
    status: str
    conflicts: tuple[str, ...] = ()
    stale_sources: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


def build_context_capsule(
    project: str,
    sources: tuple[ContextSource, ...],
    next_boundary: str,
) -> tuple[ContextCapsule | None, ContextIntegrityReport]:
    """Build a capsule only when identity, authority, freshness, and continuation are safe."""
    conflicts: list[str] = []
    stale: list[str] = []
    missing: list[str] = []
    if not project.strip():
        missing.append("project identity")
    matching = [source for source in sources if source.project == project]
    if not matching:
        missing.append("matching project source")
    for source in sources:
        if source.project != project:
            conflicts.append(f"project identity mismatch: {source.name}")
        if source.freshness != "current":
            stale.append(source.name)
    authoritative = [source for source in matching if source.authority == "canonical"]
    if len(authoritative) > 1:
        conflicts.append("multiple canonical sources")
    if not authoritative:
        missing.append("canonical source")
    if not next_boundary.strip():
        missing.append("continuation boundary")
    if conflicts or stale or missing:
        return None, ContextIntegrityReport("BLOCKED", tuple(conflicts), tuple(stale), tuple(missing))
    capsule = ContextCapsule(
        project=project,
        authoritative_sources=tuple(source.name for source in authoritative),
        facts=tuple(fact for source in authoritative for fact in source.facts),
        next_boundary=next_boundary.strip(),
    )
    return capsule, ContextIntegrityReport("READY")
