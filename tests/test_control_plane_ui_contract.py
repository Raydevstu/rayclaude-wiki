from pathlib import Path


def test_overview_passes_live_ledger_state_to_evidence_panel():
    """The overview must not present a verified ledger as unavailable."""
    source = Path("src/app.tsx").read_text(encoding="utf-8")
    assert "<Overview health={health} todayRuns={todayRuns} benchmark={benchmark} usage={usage} runs={runs} ledger={ledger} ledgerVerification={ledgerVerification} />" in source
