# Scope Guard LAB

This folder contains the isolated first prototype of Scope Guard.

## Current slice

- `scope_guard.py` defines the change contract, changed-file model, evaluator, and scope-expansion request.
- `scope_guard.py` also snapshots a workspace and derives changed files from real before/after file contents.
- `test_scope_guard.py` verifies pass, review, blocked, rollback, approval-required, and real-workspace detection behavior.
- `impact_verification_guard.py` explains observed impact and verifies identity, route, assets, rendering, and acceptance evidence.
- `test_impact_verification_guard.py` proves HTTP 200 alone is insufficient and complete evidence can verify a result.
- `context_continuity_guard.py` builds a fail-closed capsule only from current canonical context.
- `test_context_continuity_guard.py` verifies ready, stale, identity-conflict, and missing-boundary states.
- `debugging_loop_guard.py` evaluates evidence-backed debugging attempts and prevents repeated hypotheses.
- `test_debugging_loop_guard.py` verifies retain, revert, supersede, escalation, and evidence gates.
- `runtime_identity_guard.py` compares expected and observed runtime identity without changing processes or files.
- `test_runtime_identity_guard.py` verifies wrong-process, ready-runtime, and HTTP-200-without-readiness states.
- `evidence_ladder_guard.py` calibrates claims against required testing evidence and provenance.
- `test_evidence_ladder_guard.py` verifies partial, complete, blocked, provenance-preserving, synthetic, and hypothetical reports.
- `change_accountability_guard.py` audits observed files, behavior, dependencies, risks, tests, provenance, and rollback.
- `test_change_accountability_guard.py` covers synthetic overreach and a hypothetical scoped change.
- `maintainability_guard.py` checks pattern reuse, abstractions, duplication, boundaries, tests, complexity, and decisions.
- `test_maintainability_guard.py` covers synthetic maintainability debt and a hypothetical clean change.
- `cost_performance_guard.py` aggregates token, model, provider, cost, latency, retry, cache, failure, and tool-call telemetry.
- `provenance_guard.py` labels evidence and prevents non-live evidence from being treated as production proof.
- `test_cost_provenance_guard.py` verifies metric accounting, unknown cost, and provenance boundaries.
- `task_capsule_guard.py` validates current canonical context and creates a ready or blocked task capsule.
- `test_task_capsule_guard.py` covers stale/conflicting and current/continuable capsule scenarios.
- `safety_action_guard.py` applies fail-closed trust, permission, transmission, validation, confirmation, and reversibility checks.
- `test_safety_action_guard.py` covers adversarial and scoped-safe action scenarios.
- `guard_orchestrator.py` composes runtime, scope, safety, impact, and evidence guards for a browser-repair workflow.
- `test_guard_orchestrator.py` verifies complete, wrong-runtime, scope, and incomplete-evidence paths.
- `tier1_guard_adapter.py` connects the read-only browser-repair decision to the real Tier-1 FastAPI app.
- `test_tier1_guard_adapter.py` verifies the adapter refuses to claim browser proof when it is unavailable.
- `rollback_guard.py` plans an ownership-aware rollback boundary without executing it.
- `test_rollback_guard.py` covers protected user changes and irreversible-action blocking.
- `test_guard_rollback_integration.py` verifies that write actions cannot pass without a ready rollback plan.
- `evidence_matrix.py` keeps code, API, browser, journey, persistence/restart, error, benchmark, and production evidence separate.
- `test_evidence_matrix.py` rejects non-live production claims.
- `test_guard_orchestrator_adversarial.py` covers stale context, injection/secret transmission, destructive actions, and mocked evidence.
- `benchmark_guard_workflow.py` measures deterministic integrated outcomes and telemetry fields without provider calls.
- `test_benchmark_guard_workflow.py` verifies success, blocking, and zero false-success results.
- Tier-1 exposes both `GET` diagnostics and `POST /v1/guard/browser-repair` for a real user request; both remain read-only and fail closed.
- Phase 1 Quick Wins are implemented by `repository_adapter.py`, `config_loader.py`, and `quickwin_cli.py` with read-only tests in `test_quickwins.py`.

The guards are integrated into one read-only Tier-1 endpoint at `/v1/guard/browser-repair`. It inspects the current app identity and returns a truthful blocked result until live browser and journey evidence exists. It still does not edit files, launch processes, or perform rollback.
