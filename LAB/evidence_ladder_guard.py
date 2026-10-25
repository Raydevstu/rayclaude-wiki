"""Evidence calibration for real-world testing claims."""

from __future__ import annotations

from dataclasses import dataclass


LEVELS = (
    "STATIC_CHECKED", "UNIT_VERIFIED", "API_VERIFIED", "BROWSER_VERIFIED",
    "JOURNEY_VERIFIED", "PERSISTENCE_VERIFIED", "ERROR_STATE_VERIFIED",
)


@dataclass(frozen=True)
class TestContract:
    __test__ = False

    requirement: str
    required_levels: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceRecord:
    level: str
    passed: bool
    provenance: str
    details: str = ""


@dataclass(frozen=True)
class EvidenceReport:
    status: str
    covered_levels: tuple[str, ...]
    missing_levels: tuple[str, ...]
    unverified_claims: tuple[str, ...]
    provenance: tuple[str, ...]


def evaluate_evidence(contract: TestContract, records: tuple[EvidenceRecord, ...]) -> EvidenceReport:
    """Report only the confidence supported by supplied evidence."""
    missing = tuple(level for level in contract.required_levels
                    if not any(record.level == level and record.passed for record in records))
    covered = tuple(level for level in LEVELS
                    if any(record.level == level and record.passed for record in records))
    invalid = tuple(record.level for record in records if record.level not in LEVELS)
    missing = tuple(dict.fromkeys((*missing, *invalid)))
    claims = tuple(f"{contract.requirement}: {level} not verified" for level in missing)
    provenance = tuple(sorted({record.provenance for record in records}))
    status = "BLOCKED" if invalid else "VERIFIED" if not missing else "PARTIAL"
    return EvidenceReport(status, covered, missing, claims, provenance)
