"""Explicit evidence matrix; missing levels remain unverified."""

from __future__ import annotations

from dataclasses import dataclass


LEVELS = (
    "code", "api", "browser", "user_journey", "persistence_restart",
    "error_state", "benchmark", "production",
)


@dataclass(frozen=True)
class EvidenceCell:
    status: str  # passed, failed, unavailable, not_run
    provenance: str
    detail: str = ""


def build_matrix(cells: tuple[EvidenceCell, ...]) -> dict[str, EvidenceCell]:
    """Map evidence in fixed order and reject ambiguous production claims."""
    if len(cells) != len(LEVELS):
        raise ValueError(f"expected {len(LEVELS)} evidence cells")
    matrix = dict(zip(LEVELS, cells))
    production = matrix["production"]
    if production.status == "passed" and production.provenance != "live":
        raise ValueError("production evidence must be live")
    return matrix
