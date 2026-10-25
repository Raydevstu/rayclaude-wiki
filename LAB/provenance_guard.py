"""Fail-closed evidence provenance labeling."""

from __future__ import annotations

from dataclasses import dataclass


PROVENANCE = ("Live", "Local", "Mock", "Synthetic", "Cached", "Estimated", "Unavailable", "Stale", "Unauthorized")


@dataclass(frozen=True)
class EvidenceLabel:
    label: str
    detail: str = ""


@dataclass(frozen=True)
class EvidenceDecision:
    status: str
    label: str
    production_proof: bool


def classify_evidence(evidence: EvidenceLabel) -> EvidenceDecision:
    """Never upgrade mock, estimated, stale, or unknown evidence to production proof."""
    if evidence.label not in PROVENANCE:
        return EvidenceDecision("BLOCKED", "Unavailable", False)
    return EvidenceDecision(
        "VERIFIED" if evidence.label == "Live" else "LABELED",
        evidence.label,
        evidence.label == "Live",
    )
