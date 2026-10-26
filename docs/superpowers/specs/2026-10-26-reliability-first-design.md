# Reliability-First Design

## Intent

Make Tier-1 dependable for local and future multi-user operation. A task must show what success means, retain its lifecycle across a restart, and expose progress and cancellation in the control-plane UI. Production configuration must use authenticated access and durable PostgreSQL storage. Local SQLite and Ollama remain available for free development, but the UI must label their limits.

## Goals

- Add explicit task acceptance checks and return `verified`, `failed`, or `unverified` rather than treating an answer as correct by default.
- Persist task records and task events so completed work survives a restart and interrupted work is reported honestly.
- Support cancellation and safe retry from the UI.
- Use PostgreSQL when configured, report durable state accurately, and fail production startup if durable storage or authentication is missing.
- Add a session-only API-token control for the local UI when authentication is enabled.
- Replace startup-wide `Promise.all` loading with independent panel loading and remove duplicate development data requests.

## Non-goals

- Do not claim automatic recovery of an in-flight model call after a process crash. It becomes `interrupted`; an operator must retry it.
- Do not add a user account system, role database, external identity provider, or hosted deployment.
- Do not make Ollama token-price estimates look like provider invoices.
- Do not expose every existing experimental backend route in this slice; the UI focus is task reliability and recovery.

## Approaches considered

1. UI-only progress and client-side task history. Fast, but state disappears on restart and cannot support honest recovery.
2. Durable task lifecycle plus an operator UI (**selected**). Persist the lifecycle, derive UI state from the API, and mark interrupted work explicitly.
3. Distributed queue/workers. Stronger throughput and recovery, but requires an additional broker and changes the deployment model beyond this upgrade.

## Design

### Task contract

`POST /v1/tasks` accepts a prompt, mode, tier, timeout, optional spend cap, and an optional `acceptance` object. The first release supports deterministic checks:

- `contains_all`: every required case-insensitive string must appear in the final answer.
- `equals`: the normalized final answer must equal the expected text.
- `json_required_keys`: the final answer must parse as JSON and contain each named top-level key.

Task results expose `verification` with `status`, the requested checks, and per-check evidence. No acceptance object means `unverified`, never `verified`. A failed check makes the task status `failed_verification`; it does not silently become `ok`.

### Durability and recovery

Add `tasks` and `task_events` tables to the shared store schema. Each state transition writes an event to both the task event stream and the ledger. On startup, durable tasks left in `running` or `cancelling` become `interrupted` with a recovery event. Retrying creates a new task linked to its source; it never resumes a possibly side-effecting in-flight call.

SQLite remains the development default and reports `durable: false`. PostgreSQL uses the existing store implementation and reports `durable: true` only after initialization succeeds. In production, a missing/invalid PostgreSQL URL or API token prevents startup rather than falling back to SQLite or anonymous access.

### Authentication

When `TIER1_API_TOKEN` is set, API routes require `Authorization: Bearer <token>` except `/health` and `/metrics`. The Vite UI has a session-only token entry. It sends the token on API calls and never writes it to localStorage, logs, URLs, or the database. Health states explain whether authentication is disabled, configured, or required.

### UI

The `Run task` area becomes an operator panel with inputs for prompt, mode, timeout, budget, and acceptance checks. It lists recent background tasks with state, progress, verification, cancel, and retry actions. The UI polls only active tasks and stops after terminal state. Overview panels load independently; a docs failure or slow document index cannot hold the rest of the dashboard hostage. Development StrictMode is retained, but the initial data load is deduplicated.

### Evidence and measurement

Each acceptance result, retry source, cancellation, timeout, restart interruption, and authentication rejection has a ledger event. Ollama costs remain estimates unless explicit provider prices are configured, and the UI labels them as such.

## Acceptance tests

- A task with `equals` succeeds only when the final answer matches; a mismatch is `failed_verification`.
- A task without acceptance criteria is `unverified` even when execution succeeds.
- Cancelling a task records a terminal cancellation event and survives a read-after-restart.
- Startup marks a persisted running task `interrupted` and exposes it for retry.
- Production config refuses startup without PostgreSQL and an API token.
- Authenticated API requests reject a missing or invalid token and accept a valid bearer token.
- The UI renders task progress and terminal verification from the API, and does not duplicate initial data fetches in StrictMode.
- The full Python suite and production frontend build pass.

## Files and first boundary

- `tier1/store.py`, `tier1/tasks.py`, `tier1/api.py`, `tier1/services.py`, `tier1/config.py`
- `src/lib/api.ts`, `src/app.tsx`
- `tests/test_automation.py`, new focused API/auth/task tests, and frontend component tests if test infrastructure is added

Start with the persisted task schema and acceptance evaluator, prove them with failing tests, then wire API, recovery, auth, and UI in that order.
