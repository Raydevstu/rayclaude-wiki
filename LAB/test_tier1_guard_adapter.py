from pathlib import Path

from tier1_guard_adapter import inspect_browser_repair


def test_real_tier1_adapter_is_truthful_without_browser_proof():
    result = inspect_browser_repair(Path(__file__).resolve().parents[1], 8000, "Tier-1 Control Plane")
    assert result.status == "BLOCKED"
    assert result.stopped_at == "evidence"
    assert result.evidence_status == "PARTIAL"
