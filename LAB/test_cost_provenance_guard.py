from cost_performance_guard import CallRecord, summarize_calls
from provenance_guard import EvidenceLabel, classify_evidence


def test_cost_and_performance_summary_tracks_all_metrics():
    report = summarize_calls((
        CallRecord(100, 40, "model-a", "provider-a", 0.01, 120, retries=1, tool_calls=2),
        CallRecord(50, 20, "model-a", "provider-a", 0.02, 80, cache_hit=True),
    ))
    assert report.input_tokens == 150
    assert report.output_tokens == 60
    assert report.cost == 0.03
    assert report.latency_ms == 200
    assert report.retries == 1
    assert report.cache_hits == 1
    assert report.tool_calls == 2
    assert report.cost_status == "actual"


def test_unknown_cost_is_not_reported_as_zero():
    report = summarize_calls((CallRecord(10, 5, "model", "provider", None, 30),))
    assert report.cost is None
    assert report.cost_status == "unavailable"


def test_mock_and_estimated_evidence_are_not_production_proof():
    assert classify_evidence(EvidenceLabel("Mock")).production_proof is False
    assert classify_evidence(EvidenceLabel("Estimated")).production_proof is False


def test_live_evidence_can_be_verified_but_unknown_is_blocked():
    assert classify_evidence(EvidenceLabel("Live")).status == "VERIFIED"
    assert classify_evidence(EvidenceLabel("not-a-label")).status == "BLOCKED"
