# CORE-CREATION

## Scope Guard Technical Specification

### Document role

This document specifies the Scope Guard, Impact Transparency Guard, Verification Guard, Context Continuity Guard, and Debugging Loop Guard puzzle pieces. They are intended to connect later with runtime identity, project memory, and AI execution control to form the complete system.

This is a technical specification and progress record only.

## Current implementation status

**Status:** LAB slice implemented and verified.

**Implemented location:** `LAB/scope_guard.py`

**Implemented tests:**

- `LAB/test_scope_guard.py`
- `LAB/test_scope_guard_adversarial.py`

**Current evidence:** 22 LAB tests passing, including synthetic and hypothetical scenarios for scope, context continuity, and debugging-loop control.

**Not yet integrated:** Git history, live edit interception, AI execution wrapper, acceptance-test execution, automatic rollback, runtime identity collection, live browser control, and Tier-1 API integration.

## Module responsibility

Scope Guard evaluates whether a proposed or observed workspace change remains inside an approved change contract.

It is responsible for:

- Change boundary representation
- Workspace snapshot capture
- Before-and-after change detection
- Changed-line calculation
- File-layer classification
- File and line budget enforcement
- Unexpected-scope detection
- Generated-file warnings
- Destructive-change detection
- Scope-expansion approval requests
- Final scope result generation

It must not be responsible for:

- Choosing the intended running application
- Starting or stopping processes
- Browser automation
- Running arbitrary commands
- Deciding whether a dependency is semantically necessary
- Automatically applying or reverting changes
- Claiming production readiness

## Data contracts

## Impact Transparency Guard specification

**Implemented location:** `LAB/impact_verification_guard.py`

`explain_impact(changes, scope)` is read-only and converts normalized changes plus a `ScopeResult` into an `ImpactReport`.

### ImpactReport

```python
ImpactReport(
    changed_files: tuple[str, ...],
    reasons: tuple[str, ...],
    affected_layers: tuple[str, ...],
    risks: tuple[str, ...],
    rollback: str,
    status: str,
)
```

Rules:

- Every observed file is listed exactly once in `changed_files`.
- Every observed file receives a line-count and layer reason.
- Scope violations and warnings are carried into `risks`.
- Destructive changes add an explicit irreversible-operation risk.
- Rollback is `unavailable` when the scope result says rollback is unavailable.
- `status` is `REVIEW` when risks exist; otherwise it is `CLEAR`.
- The report describes observed evidence and does not infer unobserved runtime effects.

## Verification Guard specification

`VerificationEvidence` is the input contract for post-change verification. It deliberately requires more than reachability.

```python
VerificationEvidence(
    expected_project: str,
    observed_project: str,
    expected_route: str,
    observed_route: str,
    http_status: int | None,
    page_title: str,
    assets_loaded: bool,
    browser_rendered: bool,
    acceptance_passed: bool,
)
```

`verify(evidence)` returns `VerificationResult`:

```python
VerificationResult(
    status: str,                 # VERIFIED or UNVERIFIED
    failures: tuple[str, ...],
)
```

Verification rules:

1. Expected and observed project identities must match.
2. Expected and observed routes must match.
3. HTTP status must be exactly `200`.
4. A non-empty page title is required.
5. Assets must be explicitly marked loaded.
6. Browser rendering must be explicitly marked passed.
7. Acceptance criteria must be explicitly marked passed.
8. Any failed check produces `UNVERIFIED` with named failures.
9. HTTP 200 alone can never produce `VERIFIED`.

These functions evaluate supplied evidence; they do not launch a browser, inspect a process, or execute acceptance tests.

## Debugging Loop Guard specification

**Implemented location:** `LAB/debugging_loop_guard.py`

`evaluate_attempt(attempt, previous)` evaluates one debugging attempt against its evidence and prior hypotheses. It is read-only and does not apply, revert, or rerun changes.

### DebugAttempt

```python
DebugAttempt(
    failure: str,
    reproduction: str,
    evidence: tuple[str, ...],
    hypothesis: str,
    changed_files: tuple[str, ...],
    result: str,
    regression: bool = False,
    decision: str = "",
)
```

Required fields:

- `failure` identifies the observed problem.
- `reproduction` records how the problem was reproduced.
- `evidence` contains collected observations or test references.
- `hypothesis` states the proposed cause.
- `changed_files` records the attempted change boundary.
- `result` must be `fixed`, `failed`, or `inconclusive`.
- `regression` records whether related behavior was broken.

### DebugDecision

```python
DebugDecision(
    status: str,
    reason: str,
    decision: str,
)
```

Decision rules:

1. Missing failure, reproduction, evidence, or hypothesis blocks and escalates.
2. A hypothesis already present in `previous` blocks repetition and escalates.
3. A regression produces `REVIEW` with decision `revert`.
4. A `fixed` result without regression produces `VERIFIED` with decision `retain`.
5. A `failed` or `inconclusive` result produces `REVIEW` with decision `supersede`.
6. Any unknown result blocks and escalates.

The guard produces a controlled decision without claiming that the code change itself has been applied or reverted.

### ChangeContract

```python
ChangeContract(
    goal: str,
    allowed_files: tuple[str, ...] = (),
    allowed_layers: tuple[str, ...] = (),
    max_files: int = 20,
    max_changed_lines: int = 1000,
    acceptance_tests: tuple[str, ...] = (),
    risk: str = "low",
)
```

Rules:

- `goal` must be non-empty during evaluation.
- Empty `allowed_files` means no file-pattern restriction.
- Empty `allowed_layers` means no layer restriction.
- `max_files` limits all detected changed files.
- `max_changed_lines` limits the total changed-line count.
- `acceptance_tests` are recorded as contract requirements; execution is outside this slice.
- `risk` is carried into expansion requests and future approval policy.

### ChangedFile

```python
ChangedFile(
    path: str,
    changed_lines: int = 0,
    layer: str = "",
    generated: bool = False,
    destructive: bool = False,
)
```

### ScopeResult

```python
ScopeResult(
    status: str,
    score: float,
    required_changes: tuple[str, ...] = (),
    unexpected_changes: tuple[str, ...] = (),
    violations: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    rollback_available: bool = True,
)
```

Allowed statuses:

- `PASS` — no violations or warnings.
- `PARTIAL` — no blocking violations, but warnings exist.
- `REVIEW` — scope or layer violation requires review.
- `BLOCKED` — budget, destructive, or otherwise blocking violation.

## Processing flow

```text
ChangeContract
      ↓
snapshot_workspace(before)
      ↓
workspace changes occur outside this module
      ↓
snapshot_workspace(after)
      ↓
changed_files(before, after)
      ↓
evaluate(contract, changes)
      ↓
ScopeResult or expansion_request
```

## Workspace snapshot specification

`snapshot_workspace(root, ignored=())`:

- Resolves the workspace root.
- Recursively visits files.
- Stores POSIX-relative paths.
- Reads UTF-8 text files.
- Stores SHA-256 content digests.
- Skips unreadable or non-text files.
- Supports ignored glob patterns.
- Does not mutate the workspace.

The snapshot is intentionally text-focused for the LAB slice. Binary assets are currently skipped rather than evaluated.

## Change detection specification

`changed_files(before, after)` detects:

- Added files
- Modified files
- Deleted files

For text changes it calculates changed lines using a line diff. It classifies:

- UI files
- API and route files
- Data and migration files
- Configuration files
- Test files
- Build and generated files
- Utility files

Current destructive heuristics include:

- Deleted database-like files
- SQL content containing `DROP `

These heuristics are intentionally conservative and require stronger policy before production use.

## Evaluation rules

The evaluator:

1. Rejects an empty goal.
2. Checks the file-count budget.
3. Checks the changed-line budget.
4. Checks each file against allowed patterns.
5. Checks each file against allowed layers.
6. Warns on generated files.
7. Blocks destructive changes.
8. Adds a scope-expansion violation for unexpected files.
9. Warns when no acceptance tests are mapped.
10. Computes a bounded score from violations and warnings.
11. Marks rollback unavailable when a destructive change is detected.

Scoring model in the LAB slice:

```text
score = max(0, 1 - (violations × 0.20) - (warnings × 0.05))
```

The score is a diagnostic signal, not an accuracy metric or approval decision by itself.

## Scope-expansion request

`expansion_request(contract, change, reason)` returns an approval payload containing:

- Request type
- Approval-required status
- Original file boundary
- Requested file
- Requested layer
- Human-readable reason
- Contract risk level

An empty reason is rejected. The function does not approve or apply the expansion.

## Invariants

- Evaluation is read-only.
- Unexpected files are never silently accepted.
- Destructive changes cannot produce `PASS`.
- A generated-file warning remains visible in the result.
- A missing acceptance-test list cannot be represented as fully verified.
- The module does not alter files, processes, ports, databases, or browser state.
- All paths in results are workspace-relative paths.

## Verification record

The LAB verification suite currently covers:

- In-contract changes produce `PASS`.
- Unexpected files produce `REVIEW`.
- File and line budgets can produce `BLOCKED`.
- Destructive changes disable rollback availability.
- Expansion requests require a reason.
- Real before-and-after workspace snapshots detect modified, added, and deleted files.
- An adversarial multi-layer change set is blocked.
- Impact reports expose affected layers, risks, and rollback status.
- A wrong application is rejected even when it returns HTTP 200.
- Complete identity, route, asset, rendering, and acceptance evidence produces `VERIFIED`.
- A verified debugging attempt is retained only when evidence exists and no regression is reported.
- A repeated hypothesis is blocked rather than retried.
- A regression requests revert review.
- A failed or inconclusive attempt is superseded rather than treated as a solution.

The adversarial scenario detected:

- 11 changed files
- 8 unexpected files
- File-budget violation
- Line-budget violation
- Layer violations
- Destructive database change
- Generated output
- Scope expansion
- Unavailable rollback

## Known gaps

The following are deliberately outside the completed LAB slice:

- Git diff and commit-aware change ownership
- File-system event watching
- Pre-edit interception
- AI tool-call enforcement
- Dependency graph analysis
- Caller and route impact analysis
- Semantic necessity analysis
- Acceptance-test execution
- Live browser verification
- Runtime identity collection
- Automatic patch or snapshot rollback
- Persistent audit storage
- Tier-1 API integration
- Automatic debugging command execution
- Automatic patch application or rollback
- Persistent debugging-attempt storage

## Exact next boundary

The next implementation boundary is a read-only repository adapter under `LAB/` that:

1. Captures a baseline from a selected workspace.
2. Collects a Git diff when Git is available.
3. Falls back to the existing filesystem snapshot when Git is unavailable.
4. Preserves user-owned dirty changes.
5. Attributes only observed changes to the current guard run.
6. Feeds the normalized change list into the existing evaluator.

No live blocking, automatic revert, process control, browser control, or production integration belongs in that next boundary.

## Impact Transparency and Change Accountability Guard specification

**Implemented location:** `LAB/change_accountability_guard.py`

`audit_changes(contract, impacts)` produces an evidence-backed post-change accountability report.

### ChangeAccountabilityContract

```python
ChangeAccountabilityContract(
    request: str,
    allowed_files: tuple[str, ...],
)
```

### ObservedImpact

```python
ObservedImpact(
    path: str,
    functions: tuple[str, ...] = (),
    behavior: str = "",
    pre_existing: bool = False,
    generated: bool = False,
    dependencies: tuple[str, ...] = (),
    risks: tuple[str, ...] = (),
    tests: tuple[str, ...] = (),
    provenance: str = "observed",
    rollback: str = "available",
)
```

### AccountabilityReport

The report contains changed files, unexplained files, behavior, dependencies, risks, tests, provenance, and rollback instructions.

Rules:

1. Files outside `allowed_files` are unexplained and require review.
2. Dependencies, risks, tests, and provenance are deduplicated and preserved.
3. Generated files require review.
4. Any unexplained file or risk produces `REVIEW`.
5. A fully scoped change without recorded risks produces `CLEAR`.
6. The function reports supplied observations only; it does not infer unknown impact as safe.

## Maintainability and Architecture Guard specification

**Implemented location:** `LAB/maintainability_guard.py`

`evaluate_maintainability(observed)` checks supplied structural observations without changing code or making subjective edits.

### MaintainabilityInput

```python
MaintainabilityInput(
    patterns_reused: bool,
    unnecessary_abstraction: bool = False,
    duplication: bool = False,
    boundary_violation: bool = False,
    focused_tests: bool = False,
    complexity: bool = False,
    decision_record_needed: bool = False,
    dependency_concern: bool = False,
    findings: tuple[str, ...] = (),
)
```

### MaintainabilityReport

```python
MaintainabilityReport(
    status: str,                  # CLEAR, REVIEW, or BLOCKED
    findings: tuple[str, ...],
    recommendation: str,
)
```

Rules:

1. Failure to reuse an established pattern is reported.
2. Unnecessary abstraction, duplication, complexity, dependency concerns, and missing focused tests are reported.
3. Boundary violations produce `BLOCKED`.
4. Any other finding produces `REVIEW`.
5. No findings produces `CLEAR`.
6. Findings are deduplicated and preserved for review.

## Cost and Performance Guard specification

**Implemented location:** `LAB/cost_performance_guard.py`

`summarize_calls(records)` aggregates call telemetry without treating unknown cost as zero.

### CallRecord

```python
CallRecord(
    input_tokens: int,
    output_tokens: int,
    model: str,
    provider: str,
    cost: float | None,
    latency_ms: int,
    retries: int = 0,
    failed: bool = False,
    cache_hit: bool = False,
    tool_calls: int = 0,
)
```

The report aggregates input/output tokens, models, providers, cost, latency, retries, failed calls, cache hits, tool calls, and cost status. Cost status is `actual` only when every record has a cost; otherwise it is `unavailable`.

## Provenance Evidence Guard specification

**Implemented location:** `LAB/provenance_guard.py`

`classify_evidence(evidence)` validates one evidence label against the allowed provenance set:

```text
Live, Local, Mock, Synthetic, Cached, Estimated,
Unavailable, Stale, Unauthorized
```

Only `Live` produces `VERIFIED` and `production_proof=True`. All other valid labels produce `LABELED` with `production_proof=False`. Unknown labels produce `BLOCKED`.

## Context Continuity and Task Capsule Guard specification

**Implemented location:** `LAB/task_capsule_guard.py`

`validate_capsule(data)` validates continuation-critical context and returns either a versioned `TaskCapsule` or a blocked `CapsuleDecision`.

### TaskCapsuleInput

The input records project identity, canonical sources, freshness, goal, implementation state, constraints, relevant files, decisions, verification evidence, next boundary, and risks.

### Validation rules

1. Project identity, goal, implementation state, and next boundary are required.
2. Exactly one canonical source is required.
3. Freshness must be `current`.
4. Verification evidence is required.
5. Missing, stale, conflicting, or unverified context produces `BLOCKED`.
6. Valid current context produces a versioned capsule with status `READY`.
7. The validator does not infer missing facts or modify project files.

## AI Safety and Action Authorization Guard specification

**Implemented location:** `LAB/safety_action_guard.py`

`authorize_action(request)` evaluates an action request without executing it.

### ActionRequest

The request records action, target, permission, destructive state, external-content use, secret data, transmission approval, confirmation, input/output validity, and reversibility.

### Decision rules

1. External content is reported as untrusted.
2. Permissions outside `read`, `write`, and `approved-destructive` are blocked.
3. Destructive actions require explicit confirmation.
4. Secret transmission requires explicit approval.
5. Invalid input or output blocks execution.
6. Irreversible actions require confirmation.
7. Any safety finding produces `BLOCKED`.
8. Only a request with no findings produces `ALLOW`.

The function is read-only and does not execute commands, transmit data, modify files, or change databases.

## Guard Orchestrator and browser-repair workflow

**Implemented location:** `LAB/guard_orchestrator.py`

`run_browser_repair(data)` composes the existing LAB guards in this order:

```text
Runtime Identity → Scope → Safety → Impact → Evidence
```

The orchestrator stops at the first failed gate and returns the stop location plus each guard status. A successful result requires verified runtime identity, passing scope, authorized action, clear impact audit, and both browser and journey evidence.

The workflow is deterministic and read-only. It does not launch a browser, edit files, execute commands, or perform rollback.

## Controlled rollback

**Implemented location:** `LAB/rollback_guard.py`

`plan_rollback(files)` records baseline/current digests, ownership (`user`, `ai`, `generated`, or `external`), the exact AI-owned rollback boundary, protected user files, and irreversible effects. It returns `BLOCKED` until irreversible or external effects have explicit confirmation. It only plans rollback; it does not execute destructive restoration.

The orchestrator requires a ready rollback plan before a `write` action can continue. Read-only inspection remains available without a rollback plan.

## Evidence matrix

**Implemented location:** `LAB/evidence_matrix.py`

The matrix keeps `code`, `api`, `browser`, `user_journey`, `persistence_restart`, `error_state`, `benchmark`, and `production` as separate cells. A production cell can only be passed with live provenance; synthetic, mocked, estimated, cached, or local results cannot become production proof.

The current local Big Slice evidence includes browser refresh persistence, server-restart persistence, and a visible structured validation error. These remain local/mock-provider evidence and do not elevate the production cell.

## Phase 1 Quick Wins

**Implemented locations:** `LAB/repository_adapter.py`, `LAB/config_loader.py`, `LAB/quickwin_cli.py`

The repository adapter provides read-only project identity: absolute root, Git availability, branch, commit, and dirty state. The configuration loader reads explicit TOML guard thresholds (`max_files`, `max_changed_lines`, and `risk`) with validation. The CLI reports both values as JSON and performs no writes or runtime changes.

The integrated Tier-1 adapter also accepts `POST /v1/guard/browser-repair` with a real user request. It creates the task context, inspects the current project/runtime, and returns one fail-closed decision. The current implementation remains read-only and returns `BLOCKED` at missing browser evidence rather than applying a repair.

### Repository-Aware Guard Contract

**Implemented locations:** `LAB/repository_adapter.py`, `LAB/task_capsule_guard.py`, `LAB/guard_orchestrator.py`, `LAB/tier1_guard_adapter.py`

The repository-aware contract automatically captures Git root, branch, short commit, and dirty state. These values are copied into the continuation capsule and exposed by the Tier-1 browser-repair response. A write action is blocked when the repository is non-Git, the expected branch or commit does not match, or unexplained user changes are present. This is a read-only ownership gate: it does not discard, stage, commit, or revert user work.

#### Repository-aware write execution boundary

**Implemented locations:** `LAB/rollback_guard.py`, `LAB/guard_orchestrator.py`

The write boundary requires an explicit `OwnershipConfirmation` matching the inspected branch and commit and exactly enumerating AI-owned rollback files and protected user files. Dirty worktrees remain blocked without that confirmation. A ready rollback plan protects user-owned files and limits any future rollback scope to AI-owned files; the LAB implementation still plans this boundary only and does not execute writes or rollback.

#### Sandboxed write executor

**Implemented locations:** `LAB/sandboxed_write_executor.py`, `LAB/test_sandboxed_write_executor.py`

`execute_sandboxed_write()` performs a complete preflight before touching disk: it validates the ready rollback plan, exact ownership confirmation, repository identity, approved file set, repository-root containment, symlink safety, and strict SHA-256 (or explicit `missing`) baseline digests. It then writes approved UTF-8 files atomically and verifies that the resulting changed-file set and contents match the requested AI-owned diff. Protected user files and baseline drift are rejected. This is a controlled local write executor; it does not execute rollback, commit changes, or claim production authorization.

`execute_sandboxed_rollback()` now restores only the same AI-owned boundary after verifying expected post-write digests and protected-user digests. It refuses recovery when a user file changed or an AI file drifted after the write, then verifies the restored baseline. This is local rollback evidence, not production recovery or Git commit behavior.

#### Tier-1 guarded write route

**Implemented locations:** `tier1/api.py`, `LAB/test_tier1_guard_write.py`

`POST /v1/guard/write` is an explicit, opt-in adapter for the sandboxed executor. It is disabled unless `TIER1_GUARD_WRITES=1`, requires request approval, requires the exact AI/user file sets and baseline digests, inspects the live repository identity, and delegates all file safety to the LAB executor. The existing browser-repair route remains read-only. This route is local-only and not production authorization.

#### Mission Control approval UI

**Implemented locations:** `tier1/api.py`, `tier1/static/index.html`, `LAB/test_tier1_guard_approval.py`

Mission Control provides a read-only approval brief through `POST /v1/guard/approval` and a `Mission Control` UI tab. It displays proposed files and current/proposed content, AI-versus-user ownership, repository identity, risks, rollback instructions, evidence level, and whether guarded writes are enabled. It explicitly reports `write_execution: not performed`; it cannot enable or execute writes. Path escape is blocked before current-file inspection. Tier-1 writes remain disabled by default.

Approval records are persisted in the existing SQLite store through `approval_records` and can be listed or reloaded through `GET /v1/guard/approvals` and `GET /v1/guard/approvals/{id}`. Browser verification against a temporary local server proved the flow: open Mission Control, persist a proposal, reload the page, and observe the same proposal record with `BLOCKED`, rollback, ownership, and write-disabled evidence.

## Adversarial integration and benchmark

**Implemented locations:** `LAB/test_guard_orchestrator_adversarial.py`, `LAB/benchmark_guard_workflow.py`

The adversarial suite verifies fail-closed decisions for stale context, prompt injection with secret transmission, unconfirmed destructive actions, and mocked browser evidence. The deterministic benchmark reports task success, false-success rate, scope violations, latency, retries, tool calls, tokens, cost, evidence completeness, and intervention count.

### Tier-1 integration adapter

**Implemented locations:** `LAB/tier1_guard_adapter.py`, `tier1/api.py`

`GET /v1/guard/browser-repair` now runs the orchestrator against the actual Tier-1 process context. It derives the project root, current commit when available, request port, route, and expected page title. It supplies a read-only action and unavailable browser/journey evidence. The endpoint must therefore return `BLOCKED` at the evidence gate until real browser evidence is present; HTTP 200 is not treated as browser proof.
