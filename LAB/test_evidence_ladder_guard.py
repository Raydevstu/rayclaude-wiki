from evidence_ladder_guard import EvidenceRecord, TestContract, evaluate_evidence


def test_shallow_evidence_cannot_claim_complete_browser_workflow():
    report = evaluate_evidence(
        TestContract("CSV export works in browser", ("UNIT_VERIFIED", "API_VERIFIED", "JOURNEY_VERIFIED")),
        (EvidenceRecord("UNIT_VERIFIED", True, "live"), EvidenceRecord("API_VERIFIED", True, "live")),
    )
    assert report.status == "PARTIAL"
    assert report.missing_levels == ("JOURNEY_VERIFIED",)
    assert "JOURNEY_VERIFIED" in report.unverified_claims[0]


def test_complete_required_evidence_is_verified():
    report = evaluate_evidence(
        TestContract("login persists after restart", ("BROWSER_VERIFIED", "PERSISTENCE_VERIFIED")),
        (EvidenceRecord("BROWSER_VERIFIED", True, "live"),
         EvidenceRecord("PERSISTENCE_VERIFIED", True, "live")),
    )
    assert report.status == "VERIFIED"
    assert report.missing_levels == ()


def test_unknown_evidence_level_is_blocked():
    report = evaluate_evidence(
        TestContract("feature works", ("UNIT_VERIFIED",)),
        (EvidenceRecord("MADE_UP", True, "synthetic"),),
    )
    assert report.status == "BLOCKED"


def test_provenance_is_preserved():
    report = evaluate_evidence(
        TestContract("feature works", ("UNIT_VERIFIED",)),
        (EvidenceRecord("UNIT_VERIFIED", True, "mocked"),),
    )
    assert report.provenance == ("mocked",)


def test_synthetic_shallow_evidence_cannot_claim_real_world_success():
    report = evaluate_evidence(
        TestContract("checkout completes for a real user", (
            "UNIT_VERIFIED", "API_VERIFIED", "JOURNEY_VERIFIED", "ERROR_STATE_VERIFIED"
        )),
        (EvidenceRecord("UNIT_VERIFIED", True, "mocked"),
         EvidenceRecord("API_VERIFIED", True, "synthetic")),
    )
    assert report.status == "PARTIAL"
    assert set(report.missing_levels) == {"JOURNEY_VERIFIED", "ERROR_STATE_VERIFIED"}
    assert set(report.provenance) == {"mocked", "synthetic"}


def test_hypothetical_real_user_flow_is_verified_at_required_levels():
    required = ("BROWSER_VERIFIED", "JOURNEY_VERIFIED", "PERSISTENCE_VERIFIED", "ERROR_STATE_VERIFIED")
    records = tuple(EvidenceRecord(level, True, "live") for level in required)
    report = evaluate_evidence(TestContract("user can save and recover a project", required), records)
    assert report.status == "VERIFIED"
    assert report.missing_levels == ()
    assert report.provenance == ("live",)
