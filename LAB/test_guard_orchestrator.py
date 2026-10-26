from change_accountability_guard import ObservedImpact
from evidence_ladder_guard import EvidenceRecord
from guard_orchestrator import BrowserRepairInput, run_browser_repair
from runtime_identity_guard import RuntimeContract, RuntimeEvidence
from safety_action_guard import ActionRequest
from scope_guard import ChangeContract, ChangedFile
from rollback_guard import FileOwnership, OwnershipConfirmation, plan_rollback
from debugging_loop_guard import DebugAttempt
from repository_adapter import RepositoryIdentity


def workflow(**overrides):
    values = dict(
        runtime_expected=RuntimeContract("Rayclaude-wiki", "abc123", 8000, "/", "Tier-1 Control Plane"),
        runtime_observed=RuntimeEvidence("Rayclaude-wiki", "abc123", 8000, "/", "Tier-1 Control Plane", 200, True),
        changed_files=(ChangedFile("app/routes.py", 4, "utility"),),
        scope=ChangeContract("Make the app visible in the browser", ("app/routes.py",), ("utility",), 1, 10, ("browser",)),
        action=ActionRequest("edit route", "app/routes.py", "write"),
        impacts=(ObservedImpact("app/routes.py", behavior="root route restored", tests=("browser",), provenance="live"),),
        evidence=(EvidenceRecord("BROWSER_VERIFIED", True, "live"), EvidenceRecord("JOURNEY_VERIFIED", True, "live")),
        rollback=plan_rollback((FileOwnership("app/routes.py", "old", "new", "ai"),)),
        debugging=DebugAttempt("browser blank", "open /", ("title and route checked",), "route rendering", ("app/routes.py",), "fixed"),
    )
    values.update(overrides)
    return BrowserRepairInput(**values)


def test_hypothetical_browser_repair_completes_full_pipeline():
    result = run_browser_repair(workflow())
    assert result.status == "VERIFIED"
    assert result.stopped_at is None
    assert result.evidence_status == "VERIFIED"


def test_synthetic_wrong_app_stops_before_code_change():
    result = run_browser_repair(workflow(
        runtime_observed=RuntimeEvidence("Other-app", "old", 8080, "/", "Other", 200, True),
    ))
    assert result.status == "BLOCKED"
    assert result.stopped_at == "runtime"
    assert result.scope_status == "NOT_RUN"


def test_synthetic_unrelated_change_stops_at_scope():
    result = run_browser_repair(workflow(
        changed_files=(ChangedFile("docs/ROADMAP.md", 5, "utility"),),
    ))
    assert result.status == "BLOCKED"
    assert result.stopped_at == "scope"


def test_incomplete_browser_evidence_cannot_claim_repair():
    result = run_browser_repair(workflow(
        evidence=(EvidenceRecord("BROWSER_VERIFIED", True, "live"),),
    ))
    assert result.status == "BLOCKED"
    assert result.stopped_at == "evidence"


def test_dirty_repository_blocks_write_before_evidence():
    result = run_browser_repair(workflow(repository=RepositoryIdentity("/repo", True, "main", "abc123", True)))
    assert result.status == "BLOCKED"
    assert result.stopped_at == "repository"


def test_dirty_repository_reaches_guard_only_with_exact_ownership_confirmation():
    rollback = plan_rollback((
        FileOwnership("app/routes.py", "old", "new", "ai"),
        FileOwnership("notes.md", "user-old", "user-new", "user"),
    ))
    result = run_browser_repair(workflow(
        repository=RepositoryIdentity("/repo", True, "main", "abc123", True),
        rollback=rollback,
        ownership=OwnershipConfirmation("abc123", "main", ("app/routes.py",), ("notes.md",)),
    ))
    assert result.status == "VERIFIED"
    assert result.rollback_status == "app/routes.py: available"


def test_dirty_repository_rejects_unexplained_or_mismatched_ownership():
    rollback = plan_rollback((FileOwnership("app/routes.py", "old", "new", "ai"),))
    result = run_browser_repair(workflow(
        repository=RepositoryIdentity("/repo", True, "main", "abc123", True),
        rollback=rollback,
        ownership=OwnershipConfirmation("abc123", "main", ("other.py",)),
    ))
    assert result.status == "BLOCKED"
    assert result.stopped_at == "ownership"


def test_wrong_branch_and_stale_commit_block_write():
    result = run_browser_repair(workflow(
        repository=RepositoryIdentity("/repo", True, "feature", "old", False),
        expected_branch="main", expected_commit="abc123",
    ))
    assert result.status == "BLOCKED"
    assert result.stopped_at == "repository"
