from change_accountability_guard import ObservedImpact
from evidence_ladder_guard import EvidenceRecord
from guard_orchestrator import BrowserRepairInput, run_browser_repair
from rollback_guard import FileOwnership, plan_rollback
from runtime_identity_guard import RuntimeContract, RuntimeEvidence
from safety_action_guard import ActionRequest
from scope_guard import ChangeContract, ChangedFile
from debugging_loop_guard import DebugAttempt


def test_write_action_cannot_pass_without_rollback_boundary():
    result = run_browser_repair(BrowserRepairInput(
        RuntimeContract("p", "c", 8000, "/", "T"),
        RuntimeEvidence("p", "c", 8000, "/", "T", 200, True),
        (ChangedFile("app.py", 1, "utility"),),
        ChangeContract("repair", ("app.py",), ("utility",), 1, 2, ("browser",)),
        ActionRequest("edit", "app.py", "write"),
        (ObservedImpact("app.py", behavior="repair", tests=("browser",), provenance="live"),),
        (EvidenceRecord("BROWSER_VERIFIED", True, "live"), EvidenceRecord("JOURNEY_VERIFIED", True, "live")),
        debugging=DebugAttempt("blank page", "open /", ("browser evidence",), "route", ("app.py",), "fixed"),
    ))
    assert result.status == "BLOCKED"
    assert result.stopped_at == "rollback"


def test_write_action_can_reach_evidence_only_with_ready_rollback():
    rollback = plan_rollback((FileOwnership("app.py", "old", "new", "ai"),))
    assert rollback.status == "READY"
