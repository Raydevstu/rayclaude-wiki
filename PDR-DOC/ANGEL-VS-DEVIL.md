# ANGEL Vs Devil

## Proposed Plan for Resolving AI App-Building Pain Points

### Product principle

Build an evidence-driven development loop:

> Understand → Change → Test → Verify → Explain → Remember

The product should optimize for user confidence, not only code generation.

## Proposed resolutions

### 1. Over-scoped changes

- Define an explicit change boundary before implementation.
- Identify allowed files and modules.
- Show a proposed file-impact list.
- Warn when the implementation expands beyond the approved boundary.
- Prefer the smallest safe vertical slice.

### 2. False confidence

- Use evidence-based completion states: `Complete`, `Partially verified`, `Blocked`, `Failed`, and `Not tested`.
- Do not mark work complete based only on compilation or HTTP 200.
- Require the relevant validation evidence before claiming success.

### 3. Lost project context

- Maintain project memory for architecture, decisions, requirements, bugs, tests, runtime state, and preferences.
- Use compact task capsules instead of repeatedly sending the whole repository to the model.
- Preserve the exact next boundary for continuation in a new session.

### 4. Debugging loops

- Record each error, hypothesis, attempted fix, result, and affected files.
- Check previous failed approaches before proposing another fix.
- Track whether a fix was retained, reverted, or superseded.

### 5. Environment and launch confusion

Create a runtime identity panel showing:

- Project root and branch/worktree
- Process ID and port
- Database and configuration state
- Missing environment variables
- Actual page title and route
- Git commit and working-tree state

### 6. Weak real-world testing

Support separate evidence levels for:

- Static and type checks
- Unit tests
- API tests
- Browser tests
- User-journey tests
- Persistence and restart tests
- Error-state tests

### 7. Unclear changes and side effects

After each change, report:

- Files and functions changed
- Behavior added or removed
- Potential regressions
- Tests affected
- Data or migration risks
- Rollback instructions

### 8. Poor maintainability

- Reuse existing project patterns.
- Reject unnecessary abstractions.
- Require focused tests for non-trivial logic.
- Detect duplication and boundary violations.
- Record important architectural decisions.

### 9. Invisible cost and performance

Track and display:

- Input and output tokens
- Model and provider
- Estimated or actual cost
- Latency
- Retries and failed calls
- Cache hits
- Tool calls

### 10. Mock, stale, or fabricated evidence

Label every result as one of:

- Live
- Local
- Mock
- Synthetic
- Cached
- Estimated
- Unavailable
- Stale
- Unauthorized

The interface must never present mock or estimated data as production proof.

### 11. Repeated explanation

Create a reusable task capsule containing:

- User goal
- Current implementation state
- Constraints
- Relevant files
- Recent errors
- Decisions
- Verification results
- Exact next boundary

### 12. Unsafe or unclear generated behavior

- Treat external content as untrusted.
- Redact secrets before model calls.
- Detect instruction injection.
- Require confirmation before destructive changes.
- Block unapproved data or credential transmission.
- Validate inputs and outputs.
- Prefer reversible operations.

## Recommended first implementation phase

Build these five capabilities first:

1. Project and runtime identity
2. Change-impact preview
3. Real browser and API verification
4. Evidence-based completion status
5. Persistent project and task memory

These capabilities address the highest-risk failures before adding advanced benchmarking, cost optimization, or multi-agent orchestration.

## Success definition

For every AI-built change, the user should be able to answer:

- What did the AI change?
- Which application did it run?
- What was actually tested?
- What evidence proves the result?
- What remains uncertain?
- What should happen next?

## Scope boundary

This document is a proposed plan only. No implementation, deployment, production integration, or external connector work is authorized by this document alone.
