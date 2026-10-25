from test_guard_orchestrator import workflow
from guard_orchestrator import run_browser_repair
from context_continuity_guard import ContextSource
from task_capsule_guard import TaskCapsuleInput
from safety_action_guard import ActionRequest
from evidence_ladder_guard import EvidenceRecord
from change_accountability_guard import ObservedImpact


def test_stale_context_stops_before_runtime():
    context = TaskCapsuleInput("p", ("CORE.md",), "stale", "goal", "state", (), (), (), ("health",), "next")
    result = run_browser_repair(workflow(context=context))
    assert result.stopped_at == "context"


def test_prompt_injection_and_secret_transmission_stop_at_safety():
    result = run_browser_repair(workflow(action=ActionRequest("edit", "app.py", "write", external_content=True,
                                           secret_data=True, transmit_data=True)))
    assert result.stopped_at == "safety"


def test_destructive_migration_stops_at_safety():
    result = run_browser_repair(workflow(action=ActionRequest("drop database", "db.sql", "approved-destructive",
                                           destructive=True, confirmed=False)))
    assert result.stopped_at == "safety"


def test_mocked_browser_evidence_cannot_claim_verified_repair():
    result = run_browser_repair(workflow(evidence=(EvidenceRecord("BROWSER_VERIFIED", True, "mock"),
                                EvidenceRecord("JOURNEY_VERIFIED", True, "mock"))))
    assert result.stopped_at == "evidence"
    assert result.status == "BLOCKED"
