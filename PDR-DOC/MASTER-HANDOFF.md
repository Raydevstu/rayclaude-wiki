# Rayclaude Wiki — Master Handoff

## Current boundary

The current foundation, LAB trust boundary, and asynchronous sandbox job slice are implemented. The governed execution pipeline remains write-disabled by default.

## Implemented and evidenced

- Core guard family exists under `LAB/`.
- Git repository identity is connected; branch/commit/worktree state is available.
- Guard orchestrator, approval preview, sandbox lifecycle, controlled write/rollback boundaries, and Mission Control sandbox health UI exist.
- Sandbox provisioning is asynchronous (`202` + job id), reports phase progress, supports cooperative cancellation, and never publishes a partial sandbox.
- Sandbox cleanup is asynchronous with observable `FAILED`, `REMOVED`, and expired-sweep job states; managed Git commands disable inherited user hooks.
- Sandbox job snapshots persist in the existing SQLite store; manager restart reloads terminal jobs and marks in-flight jobs interrupted, while expiry cleanup derives truth from sandbox manifests.
- Mission Control polls sandbox jobs and exposes cancellation while preserving the approval and rollback boundary.
- Writes remain disabled by default.
- Focused sandbox/approval/API verification: 21 passed.
- Browser evidence: local Mission Control showed provisioning at 5%, 55%, and 85%, then a managed sandbox in `READY` state.
- Full suite: 63 passed, 3 failures remain at the host boundary: Windows `_overlapped`/Winsock subprocess startup affects CLI and MCP stdio tests. The optional `pypdf` dependency is installed for this environment, and the MCP tool-count assertion now matches the 12-tool contract.
- Preview evidence: `http://127.0.0.1:8001/` returned the Tier-1 title and Mission Control; browser provisioning visibly reached `5% copying` and `READY` with repository branch `main`. Preview artifacts were removed afterward.
- `python -m compileall -q tier1 LAB`: passed.

## Exact next implementation boundary

The next boundary is operational hardening of persisted job retention and concurrent cleanup scheduling. Preserve the existing approval, evidence, repository-identity, sandbox, and rollback gates. Do not enable production writes or claim live-agent integration.

## Current risks and gaps

- The worktree is intentionally dirty and uncommitted; preserve all existing changes.
- Browser evidence uses the Codex in-app browser fallback; the `bsk` daemon was blocked by host socket policy.
- Production deployment, real provider-agent execution, automatic rollback execution, and large-repository provisioning remain unverified.
- The Windows subprocess provider issue requires host repair or a different test host; it is not fixed in application code.

## Codex operating note

This file is the compact continuation capsule for a new chat. Use it together with `AGENTS.md`, current code, and the test results above. Do not delete durable project memory to reduce chat context. Keep future responses concise and avoid re-sending the repository or historical debate unless needed.

## New-chat first action

Read this handoff, inspect the dirty worktree, then harden persisted job retention and concurrent cleanup scheduling before expanding scope.
