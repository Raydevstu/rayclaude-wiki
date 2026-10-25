"""LAB orchestration for one safe browser-repair workflow."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from .change_accountability_guard import ChangeAccountabilityContract, ObservedImpact, audit_changes
    from .evidence_ladder_guard import EvidenceRecord, TestContract, evaluate_evidence
    from .runtime_identity_guard import RuntimeContract, RuntimeEvidence, inspect_runtime
    from .safety_action_guard import ActionRequest, authorize_action
    from .scope_guard import ChangeContract, ChangedFile, evaluate
    from .task_capsule_guard import TaskCapsuleInput, validate_capsule
    from .cost_performance_guard import CallRecord, summarize_calls
    from .rollback_guard import RollbackPlan, OwnershipConfirmation, ownership_mismatch
    from .debugging_loop_guard import DebugAttempt, evaluate_attempt
    from .repository_adapter import RepositoryIdentity, repository_mismatch
except ImportError:  # pytest's LAB path keeps the original standalone imports working.
    from change_accountability_guard import ChangeAccountabilityContract, ObservedImpact, audit_changes
    from evidence_ladder_guard import EvidenceRecord, TestContract, evaluate_evidence
    from runtime_identity_guard import RuntimeContract, RuntimeEvidence, inspect_runtime
    from safety_action_guard import ActionRequest, authorize_action
    from scope_guard import ChangeContract, ChangedFile, evaluate
    from task_capsule_guard import TaskCapsuleInput, validate_capsule
    from cost_performance_guard import CallRecord, summarize_calls
    from rollback_guard import RollbackPlan, OwnershipConfirmation, ownership_mismatch
    from debugging_loop_guard import DebugAttempt, evaluate_attempt
    from repository_adapter import RepositoryIdentity, repository_mismatch


@dataclass(frozen=True)
class BrowserRepairInput:
    runtime_expected: RuntimeContract
    runtime_observed: RuntimeEvidence
    changed_files: tuple[ChangedFile, ...]
    scope: ChangeContract
    action: ActionRequest
    impacts: tuple[ObservedImpact, ...]
    evidence: tuple[EvidenceRecord, ...]
    context: TaskCapsuleInput | None = None
    calls: tuple[CallRecord, ...] = ()
    rollback: RollbackPlan | None = None
    debugging: DebugAttempt | None = None
    repository: RepositoryIdentity | None = None
    expected_branch: str | None = None
    expected_commit: str | None = None
    ownership: OwnershipConfirmation | None = None


@dataclass(frozen=True)
class BrowserRepairResult:
    status: str
    stopped_at: str | None
    reason: str
    scope_status: str
    runtime_status: str
    safety_status: str
    impact_status: str
    evidence_status: str
    context_status: str = "NOT_RUN"
    cost_status: str = "NOT_RUN"
    rollback_status: str = "not applicable"


def run_browser_repair(data: BrowserRepairInput) -> BrowserRepairResult:
    """Run the safe LAB pipeline; no files, processes, or browsers are changed."""
    context_status = "NOT_RUN"
    if data.context is not None:
        _, context = validate_capsule(data.context)
        context_status = context.status
        if context.status != "READY":
            return BrowserRepairResult("BLOCKED", "context", "task context is not safe to continue",
                                       "NOT_RUN", "NOT_RUN", "NOT_RUN", "NOT_RUN", "NOT_RUN",
                                       context_status, "NOT_RUN")
    runtime = inspect_runtime(data.runtime_expected, data.runtime_observed)
    if runtime.status != "READY":
        return BrowserRepairResult("BLOCKED", "runtime", runtime.recommendation,
                                   "NOT_RUN", runtime.status, "NOT_RUN", "NOT_RUN", "NOT_RUN",
                                   context_status)
    scope = evaluate(data.scope, list(data.changed_files))
    if scope.status in {"BLOCKED", "REVIEW"}:
        return BrowserRepairResult("BLOCKED", "scope", "scope contract failed",
                                   scope.status, runtime.status, "NOT_RUN", "NOT_RUN", "NOT_RUN",
                                   context_status)
    safety = authorize_action(data.action)
    if data.action.permission == "write" and data.repository is not None:
        mismatch = repository_mismatch(data.repository, data.expected_branch, data.expected_commit)
        if mismatch:
            return BrowserRepairResult("BLOCKED", "repository", mismatch,
                                       scope.status, runtime.status, "BLOCKED", "NOT_RUN", "NOT_RUN",
                                       context_status, "NOT_RUN", "missing")
        if data.repository.dirty and data.ownership is None:
            return BrowserRepairResult("BLOCKED", "repository",
                                       "working tree has unexplained user changes; explicit ownership confirmation is required",
                                       scope.status, runtime.status, "BLOCKED", "NOT_RUN", "NOT_RUN",
                                       context_status, "NOT_RUN", "missing")
    if data.action.permission == "write" and data.rollback is None:
        return BrowserRepairResult("BLOCKED", "rollback", "write action has no rollback boundary",
                                   scope.status, runtime.status, "BLOCKED", "NOT_RUN", "NOT_RUN",
                                   context_status, "NOT_RUN", "missing")
    if data.rollback is not None and data.rollback.status != "READY":
        return BrowserRepairResult("BLOCKED", "rollback", "rollback boundary is not ready",
                                   scope.status, runtime.status, "BLOCKED", "NOT_RUN", "NOT_RUN",
                                   context_status, "NOT_RUN", data.rollback.status)
    if data.action.permission == "write" and data.repository is not None and data.rollback is not None:
        ownership_reason = ownership_mismatch(
            data.rollback, data.ownership,
            repository_commit=data.repository.commit,
            repository_branch=data.repository.branch,
        )
        if ownership_reason:
            return BrowserRepairResult("BLOCKED", "ownership", ownership_reason,
                                       scope.status, runtime.status, "BLOCKED", "NOT_RUN", "NOT_RUN",
                                       context_status, "NOT_RUN", data.rollback.status)
    if safety.status != "ALLOW":
        return BrowserRepairResult("BLOCKED", "safety", safety.recommendation,
                                   scope.status, runtime.status, safety.status, "NOT_RUN", "NOT_RUN",
                                   context_status)
    if data.action.permission == "write" and data.debugging is None:
        return BrowserRepairResult("BLOCKED", "debugging", "write action has no debugging record",
                                   scope.status, runtime.status, safety.status, "NOT_RUN", "NOT_RUN",
                                   context_status, "NOT_RUN", data.rollback.status if data.rollback else "missing")
    if data.debugging is not None:
        debug = evaluate_attempt(data.debugging)
        if debug.status != "VERIFIED":
            return BrowserRepairResult("BLOCKED", "debugging", debug.reason,
                                       scope.status, runtime.status, safety.status, "NOT_RUN", "NOT_RUN",
                                       context_status, "NOT_RUN", data.rollback.status if data.rollback else "missing")
    impact = audit_changes(ChangeAccountabilityContract(data.scope.goal, data.scope.allowed_files), data.impacts)
    if impact.status != "CLEAR":
        return BrowserRepairResult("BLOCKED", "impact", "impact review required",
                                   scope.status, runtime.status, safety.status, impact.status, "NOT_RUN",
                                   context_status, "NOT_RUN", "; ".join(impact.rollback) or "none")
    evidence = evaluate_evidence(TestContract(data.scope.goal, ("BROWSER_VERIFIED", "JOURNEY_VERIFIED")), data.evidence)
    required = {"BROWSER_VERIFIED", "JOURNEY_VERIFIED"}
    non_live = tuple(record.level for record in data.evidence
                     if record.level in required and record.passed and record.provenance != "live")
    if non_live or evidence.status != "VERIFIED":
        return BrowserRepairResult("BLOCKED", "evidence", "browser repair is not fully verified",
                                   scope.status, runtime.status, safety.status, impact.status, evidence.status,
                                   context_status, summarize_calls(data.calls).cost_status if data.calls else "NOT_RUN",
                                   "; ".join(impact.rollback) or "none")
    cost_status = summarize_calls(data.calls).cost_status if data.calls else "NOT_RUN"
    return BrowserRepairResult("VERIFIED", None, "browser repair evidence is complete",
                               scope.status, runtime.status, safety.status, impact.status, evidence.status,
                               context_status, cost_status, "; ".join(impact.rollback) or "none")
