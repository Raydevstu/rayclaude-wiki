import pytest

from evidence_matrix import EvidenceCell, build_matrix


def test_real_browser_slice_keeps_other_evidence_levels_separate():
    matrix = build_matrix(tuple(
        EvidenceCell("passed", "local") if level in {"code", "api", "browser", "user_journey"}
        else EvidenceCell("not_run", "unavailable")
        for level in ("code", "api", "browser", "user_journey", "persistence_restart", "error_state", "benchmark", "production")
    ))
    assert matrix["browser"].status == "passed"
    assert matrix["user_journey"].status == "passed"
    assert matrix["production"].status == "not_run"


def test_non_live_production_claim_is_rejected():
    cells = [EvidenceCell("not_run", "unavailable") for _ in range(8)]
    cells[-1] = EvidenceCell("passed", "synthetic")
    with pytest.raises(ValueError, match="production evidence must be live"):
        build_matrix(tuple(cells))
