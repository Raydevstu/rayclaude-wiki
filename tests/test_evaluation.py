import json

import pytest

from tier1.evaluation import (
    CaseResult,
    EvaluationReport,
    PRIORITIES,
    evaluate_results,
    render_markdown,
    run_evaluation,
)


def test_priorities_cover_all_ten_pain_points():
    assert tuple(p["number"] for p in PRIORITIES) == tuple(range(1, 11))
    assert len(PRIORITIES) == 10


def test_evaluation_score_counts_only_passed_results():
    results = [
        CaseResult("p1", 1, "passed", "api", "real", {}, "ok"),
        CaseResult("p2", 2, "failed", "code", "real", {}, "bad"),
        CaseResult("p3", 3, "unavailable", "browser", "unavailable", {}, "no session"),
    ]
    report = evaluate_results(results, timestamp="2026-10-26T00:00:00Z")
    assert report.score == pytest.approx(1 / 3)
    assert report.priority_status[1] == "passed"
    assert report.priority_status[2] == "failed"
    assert report.priority_status[3] == "unavailable"


def test_mock_evidence_cannot_claim_production():
    with pytest.raises(ValueError, match="production"):
        CaseResult("bad", 1, "passed", "production", "mock", {}, "synthetic")


def test_report_serializes_json_and_markdown_with_caveat():
    result = CaseResult("p1", 1, "passed", "api", "mock", {"latency_ms": 4}, "synthetic")
    report = evaluate_results([result], timestamp="2026-10-26T00:00:00Z")
    payload = report.to_dict()
    assert json.loads(json.dumps(payload))["timestamp"] == "2026-10-26T00:00:00Z"
    markdown = render_markdown(report)
    assert "Mock or synthetic evidence" in markdown
    assert "False confidence" in markdown


def test_report_requires_known_status_and_evidence_level():
    with pytest.raises(ValueError):
        CaseResult("bad", 1, "done", "api", "real", {}, "invalid")


def test_run_evaluation_returns_all_priorities_and_marks_live_gates_unavailable(settings):
    from tier1 import services

    svc = services.build(settings)
    report = run_evaluation(svc)
    assert len(report.results) >= 10
    assert {r.priority for r in report.results} == set(range(1, 11))
    assert any(r.evidence_level == "browser" and r.status == "unavailable" for r in report.results)
    assert any(r.evidence_level == "production" and r.status == "unavailable" for r in report.results)
    assert report.score == pytest.approx(0.8)
