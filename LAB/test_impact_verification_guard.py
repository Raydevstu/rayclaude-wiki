from impact_verification_guard import (
    VerificationEvidence,
    explain_impact,
    verify,
)
from scope_guard import ChangedFile, ScopeResult


def test_impact_report_explains_scope_and_rollback():
    scope = ScopeResult("BLOCKED", 0.0, violations=("scope expansion",), rollback_available=False)
    report = explain_impact([
        ChangedFile("db/migration.sql", 4, "data", destructive=True),
        ChangedFile("src/export.py", 3, "utility"),
    ], scope)
    assert report.status == "REVIEW"
    assert report.affected_layers == ("data", "utility")
    assert report.rollback == "unavailable"
    assert any("db/migration.sql" in risk for risk in report.risks)


def test_verification_does_not_accept_http_200_alone():
    result = verify(VerificationEvidence(
        "Tier-1", "Wrong app", "http://127.0.0.1:8000/", "http://127.0.0.1:8080/",
        200, "Context Governor", True, True, True,
    ))
    assert result.status == "UNVERIFIED"
    assert "project identity mismatch" in result.failures
    assert "route mismatch" in result.failures


def test_verification_accepts_complete_evidence():
    result = verify(VerificationEvidence(
        "Tier-1", "Tier-1", "http://127.0.0.1:8000/", "http://127.0.0.1:8000/",
        200, "Tier-1 Control Plane", True, True, True,
    ))
    assert result.status == "VERIFIED"
