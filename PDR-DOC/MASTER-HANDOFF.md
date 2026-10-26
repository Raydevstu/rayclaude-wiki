# Rayclaude Wiki — Master Handoff

## Current boundary

The current foundation and LAB trust boundary are implemented. The next product slice is to continue the governed execution pipeline without enabling uncontrolled writes.

## Implemented and evidenced

- Core guard family exists under `LAB/`.
- Git repository identity is connected; branch/commit/worktree state is available.
- Guard orchestrator, approval preview, sandbox lifecycle, controlled write/rollback boundaries, and Mission Control sandbox health UI exist.
- Writes remain disabled by default.
- Full LAB verification: 98 passed.
- Focused sandbox/API verification: 3 passed.
- `git diff --check`: passed.

## Exact next implementation boundary

Build asynchronous sandbox provisioning with progress, cancellation, and cleanup-job status. Preserve the existing approval, evidence, repository-identity, sandbox, and rollback gates. Do not enable production writes or claim live-agent integration until the async workflow has direct API and browser evidence.

## Current risks and gaps

- The worktree is intentionally dirty and uncommitted; preserve all existing changes.
- Live browser verification of the newest sandbox health/list controls has not been rerun.
- Production deployment, real provider-agent execution, automatic rollback execution, and large-repository provisioning remain unverified.
- The memory-service lookup for this handoff failed in the current turn. Ray Orca/Memmy memory must be treated as unconfirmed until a future lookup succeeds.

## Codex operating note

This file is the compact continuation capsule for a new chat. Use it together with `AGENTS.md`, current code, and the test results above. Do not delete durable project memory to reduce chat context. Keep future responses concise and avoid re-sending the repository or historical debate unless needed.

## New-chat first action

Read this handoff, inspect the dirty worktree, then implement and test the asynchronous sandbox job slice before expanding scope.
