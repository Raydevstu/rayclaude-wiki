# God-list

## Scope Guard Decision

### Status

**Final direction:** Scope Guard v2, contract-driven and evidence-based.

Scope Guard v1 remains the foundational model and historical baseline. It is not a separate implementation target.

## Pain Point Covered

**Over-scoped AI changes** — AI changes too many files, modules, or architectural layers when the user requested a focused change.

## Initial Proposed Resolution: Scope Guard v1

The initial proposal was to create a Scope Guard that controls the implementation boundary before, during, and after coding.

It would:

- Create a change contract from the user request.
- Define allowed files and modules.
- Identify expected tests and acceptance criteria.
- Analyze callers, imports, routes, schemas, fixtures, and dependencies.
- Set a diff budget for files, lines, modules, or architectural layers.
- Require justification for files outside the original boundary.
- Protect data, migrations, configuration, and destructive operations.
- Pause for user approval when scope expands materially.
- Track the AI-owned change set for rollback.
- Audit the final diff against the original request.

### Initial change contract

```json
{
  "goal": "Add a CSV export button",
  "allowed_files": [
    "components/export-button.tsx",
    "lib/export/csv.ts",
    "tests/export.test.ts"
  ],
  "allowed_layers": ["ui", "utility", "test"],
  "max_files": 4,
  "max_changed_lines": 250,
  "acceptance_tests": [
    "CSV downloads successfully",
    "Special characters are escaped",
    "Existing export behavior remains unchanged"
  ]
}
```

## Final Proposed Resolution: Scope Guard v2

Scope Guard v2 is a contract-driven scope control system that plans the allowed change, monitors implementation, negotiates justified expansion, and audits the final result.

### 1. Scope Planner

Before coding, produce a change contract containing:

- User goal
- Acceptance criteria
- Candidate files
- Allowed modules and layers
- Expected tests
- Risk level
- Initial diff budget
- Prohibited areas

Show the contract before implementation begins when the task is cross-module or high-risk.

### 2. Scope Monitor

During implementation, monitor:

- File edits
- New dependencies
- Imports and callers
- Routes and schemas
- Database or migration changes
- Generated files
- Shell commands
- Network access
- Destructive operations

Classify each action as:

- Allowed
- Unexpected but explainable
- Risky
- Blocked

### 3. Scope Negotiator

When the AI needs to expand scope, it must stop silently expanding and provide:

- Original boundary
- New requested files or layers
- Reason for expansion
- Acceptance criterion requiring it
- Risk introduced
- Smaller alternatives
- Approval options

Example:

```text
Scope expansion requested

Original boundary:
- 3 files
- UI and utility layers

New request:
- Add database migration
- Modify authentication middleware

Reason:
- Existing API cannot persist the new field

Risk:
- Existing records require migration

Options:
1. Approve expansion
2. Use a smaller non-persistent implementation
3. Stop and revise the plan
```

### 4. Scope Auditor

After implementation, compare:

- Original request
- Change contract
- Actual diff
- Tests and acceptance criteria
- Runtime behavior
- Unapproved scope expansion
- Maintainability impact
- Rollback safety

The audit should report:

- Required changes completed
- Unexpected changes
- Unverified dependency impact
- Data or security risk
- Test coverage and evidence level
- Rollback availability

### 5. Scope tiers

#### Tier 1: Small safe change

Examples include text changes, isolated UI adjustments, and small local bug fixes. Automatic approval is acceptable when the change remains within the contract.

#### Tier 2: Cross-module change

Examples include API plus UI changes, shared utility changes, and new routes or workers. Require dependency analysis, focused tests, and a final scope audit.

#### Tier 3: High-risk change

Examples include database migrations, authentication, payments, production configuration, and destructive data operations. Require explicit approval before implementation and before final application.

## Coverage of the 10 over-scope controls

| Control | Scope Guard v2 capability |
|---|---|
| Goal decomposition | Scope Planner and change contract |
| Scope classification | Candidate file, module, and layer map |
| Dependency impact analysis | Scope Monitor dependency scanner |
| Diff budget | Contract limits and enforcement |
| Change justification | Scope Negotiator |
| Data and migration protection | Risk gate and Tier 3 approval |
| Acceptance-test mapping | Contract-linked acceptance criteria |
| User approval checkpoint | Scope Negotiator approval state |
| Rollback boundary | AI-owned change-set tracking |
| Post-change scope audit | Scope Auditor |

## Completion example

```text
Scope result: PARTIAL
Required changes: complete
Unexpected changes: 1
Unverified dependency impact: 1
Data risk: none
Rollback: available
Acceptance criteria: 2/3 passed
Recommendation: review before merge
```

## Decision record

The initial Scope Guard proposal was intentionally small: establish an allowed boundary, monitor the diff, and review the result.

The debate showed that a file allowlist alone is insufficient. Scope can expand through dependencies, generated files, migrations, commands, configuration, and architectural decisions even when the original files are correctly identified.

Therefore, Scope Guard v2 adds intent control, dependency analysis, change-budget enforcement, risk gates, explicit scope negotiation, tiered approval, rollback tracking, and post-change accountability.

## Implementation boundary

This document defines the final design direction only. It does not authorize implementation, deployment, production integration, external connector work, destructive changes, or database migrations by itself.

## LAB Phase Completion Boundary

The LAB phase is complete for all three guards:

- Scope Guard
- Impact Transparency Guard
- Verification Guard

The functions are still isolated prototypes; they are not yet connected to the real AI agent, Tier-1 API, live browser, or automatic rollback. That integration is the remaining product-level boundary, not an unfinished LAB test.

## Pain Point 5: Runtime Identity and Launch Guard

Runtime Identity and Launch Guard is a read-only control that establishes runtime identity before allowing launch or repair actions.

Its unique boundary is between:

- the application the user intended;
- the application actually running;
- the environment being inspected;
- the environment being modified;
- evidence that the application is ready; and
- actions that require approval.

The LAB proposition is to:

1. Build an expected runtime contract.
2. Collect observed project, commit, process, port, route, title, HTTP, and readiness evidence.
3. Compare expected and observed identity.
4. Classify mismatches.
5. Refuse to recommend code changes when the wrong application or environment is active.
6. Return the smallest safe next recommendation.

Core decision flow:

```text
Expected runtime contract
        ↓
Observed runtime evidence
        ↓
Identity and consistency comparison
        ↓
Mismatch classification
        ↓
Readiness decision
        ↓
Safe recommendation
```

Example mismatch result:

```text
Status: UNVERIFIED
Expected: Rayclaude-wiki / port 8000 / Tier-1 Control Plane
Observed: Other-app / port 8080 / Context Governor
Decision: do not edit application files
Recommendation: launch or inspect the intended application
```

The first implementation is `LAB/runtime_identity_guard.py`. It does not kill processes, change ports, modify environment variables, alter databases, launch applications, or control browsers.

## Pain Point 6: Evidence Ladder and Real-World Test Guard

Evidence Ladder and Real-World Test Guard maps requirements to the minimum evidence needed for a truthful claim. It calibrates evidence rather than treating every passing test as proof of complete application behavior.

Supported evidence levels:

```text
STATIC_CHECKED
UNIT_VERIFIED
API_VERIFIED
BROWSER_VERIFIED
JOURNEY_VERIFIED
PERSISTENCE_VERIFIED
ERROR_STATE_VERIFIED
UNVERIFIED
BLOCKED
```

The LAB contract contains a requirement and required evidence levels. Each evidence record contains its level, pass state, provenance, and details. The evaluator returns covered levels, missing levels, unsupported claims, provenance, and status.

Rules:

- Missing required evidence produces `PARTIAL`.
- Unknown evidence levels produce `BLOCKED`.
- Complete required evidence produces `VERIFIED`.
- Provenance is preserved and never silently upgraded.
- Lower-level evidence cannot claim a missing higher-level user journey.

The first implementation is `LAB/evidence_ladder_guard.py`. It evaluates supplied evidence only; it does not run tests, control browsers, or fabricate results.

## Pain Point 3: Context Continuity Guard

Context Continuity Guard is a read-only, evidence-based context control layer that creates a verified Task Continuity Capsule before the AI acts.

It validates:

- project identity;
- authoritative source;
- information freshness;
- relevant context;
- previous failures and decisions; and
- the exact continuation boundary.

The guard is fail-closed:

- uncertain project identity blocks continuation;
- conflicting canonical sources are reported;
- stale context is labelled and blocks the capsule;
- missing information is reported rather than invented;
- low-confidence retrieval cannot silently continue; and
- a missing safe continuation boundary requires review.

The LAB proposition produces three outputs:

1. Context Capsule — relevant verified facts and decisions.
2. Context Integrity Report — conflicts, stale sources, missing information, and status.
3. Continuation Boundary — completed work, unresolved risks, and the next safe action.

The first implementation is located at `LAB/context_continuity_guard.py`. It does not modify project files or claim context that is not present in a current canonical source.
