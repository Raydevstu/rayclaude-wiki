# Reliability-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Tier-1 tasks verifiable, durable across restarts, securely accessible in production, and operable from the control-plane UI.

**Architecture:** Persist task lifecycle and events in the shared store, then make task execution report deterministic acceptance results. The API becomes the source of truth for task recovery and token enforcement. The React UI polls only active tasks and independently loads non-critical dashboard panels.

**Tech Stack:** Python 3.14, FastAPI, SQLite/PostgreSQL, pytest, React, TypeScript, Vite.

**Spec:** `docs/superpowers/specs/2026-10-26-reliability-first-design.md`

## Global Constraints

- Preserve SQLite and Ollama for free local development, clearly labeled as non-durable/estimated.
- Production requires PostgreSQL and `TIER1_API_TOKEN`; it must not silently fall back to anonymous SQLite.
- Never resume an in-flight model call after restart; mark it `interrupted` and require an explicit retry.
- API tokens are session-only in the browser and never persisted, logged, placed in URLs, or written to the database.
- New behavior follows test-driven development with a witnessed failing test before implementation.

## Review Focus

- A task without acceptance criteria must be `unverified`, not `verified` — Task 1.
- A final answer that misses one required term must be `failed_verification` — Task 1.
- A restart while a task is running must produce `interrupted`, not `done` — Task 2.
- A configured token must reject missing and incorrect bearer tokens on protected routes — Task 3.
- A slow docs endpoint must not delay task and evidence data in the dashboard — Task 4.

---

## File structure

- `tier1/verification.py`: deterministic acceptance evaluator and typed result payload.
- `tier1/store.py`: shared task/event schema and SQLite persistence methods.
- `tier1/postgres_store.py`: PostgreSQL compatibility for the new schema.
- `tier1/tasks.py`: durable lifecycle, cancellation, retry, and startup reconciliation.
- `tier1/api.py`: request models, protected-route token dependency, task endpoints.
- `tier1/config.py`, `tier1/services.py`: production validation and startup recovery.
- `src/lib/api.ts`: token-aware fetch and task API client.
- `src/app.tsx`: independent loading and task operator panel.
- `tests/test_automation.py`, `tests/test_api_auth.py`, `tests/test_verification.py`: focused behavior coverage.

### Task 1: Acceptance evaluation and task outcome contract

**Files:**
- Create: `tier1/verification.py`
- Modify: `tier1/tasks.py`
- Test: `tests/test_verification.py`

**Interfaces:**
- Produces: `evaluate_acceptance(answer: str, acceptance: dict | None) -> dict` with `status` in `verified|failed_verification|unverified` and per-check results.
- Consumes: `Tasks._go()` final run result and adds `verification` before persisting a terminal state.

- [ ] Write failing tests for no criteria (`unverified`), an exact match (`verified`), a missed `contains_all` term, and missing JSON key (`failed_verification`).
- [ ] Run `pytest -q tests/test_verification.py`; expect failure because the evaluator does not exist.
- [ ] Implement `evaluate_acceptance` with normalized exact text, case-insensitive contains checks, and JSON top-level key checks.
- [ ] Update task completion so successful execution with failed checks becomes `failed_verification` and emits an evidence event.
- [ ] Run `pytest -q tests/test_verification.py tests/test_automation.py`; expect pass.
- [ ] Commit the focused task changes.

### Task 2: Durable task lifecycle, restart recovery, cancellation, and retry

**Files:**
- Modify: `tier1/store.py`, `tier1/postgres_store.py`, `tier1/tasks.py`, `tier1/services.py`
- Modify: `tests/test_automation.py`, `LAB/test_store_backends.py`

**Interfaces:**
- Produces: `Store.task_put`, `task_get`, `tasks_list`, `task_event_add`, `task_events`, and `reconcile_interrupted_tasks`.
- Produces: `Tasks.cancel(task_id) -> dict`, `Tasks.retry(task_id) -> str`, and startup reconciliation.
- Consumes: Task verification data from Task 1.

- [ ] Write failing tests for persisted lifecycle/event round-trip, cancellation, retry linkage, and restart conversion from `running` to `interrupted`.
- [ ] Run the focused tests; expect failure because task persistence methods do not exist.
- [ ] Add shared schema tables and store methods, then ensure PostgreSQL initializes them idempotently.
- [ ] Persist every state transition and ledger event; retry creates a new record with `retry_of`, never reuses the old one.
- [ ] Reconcile running/cancelling tasks at service startup.
- [ ] Run focused task/store tests; expect pass.
- [ ] Commit the durable lifecycle changes.

### Task 3: Production-safe storage and bearer-token authentication

**Files:**
- Modify: `tier1/config.py`, `tier1/api.py`, `tier1/services.py`
- Create: `tests/test_api_auth.py`
- Modify: `tests/test_core.py`, `LAB/test_store_backends.py`

**Interfaces:**
- Produces: `Settings.validate_runtime() -> None` and a FastAPI dependency `require_api_token`.
- Consumes: `TIER1_ENV`, `TIER1_DATABASE_URL`, and `TIER1_API_TOKEN`.

- [ ] Write failing tests proving production refuses missing PostgreSQL/token, protected routes reject missing/invalid bearer tokens, and health/metrics remain available.
- [ ] Run `pytest -q tests/test_api_auth.py`; expect failure because validation and route dependency are absent.
- [ ] Implement explicit production validation and apply the dependency to `/v1/*` routes while preserving health/metrics probes.
- [ ] Add health fields for storage durability and authentication state without exposing token data.
- [ ] Run focused auth/config tests plus existing API tests; expect pass.
- [ ] Commit the runtime hardening changes.

### Task 4: Operator UI for task progress, cancellation, retry, and independent loading

**Files:**
- Modify: `src/lib/api.ts`, `src/app.tsx`
- Create: `src/lib/tasks.ts` if extraction keeps the component focused
- Test: add the project’s minimal frontend test setup or use a browser regression check if existing tooling cannot support component tests

**Interfaces:**
- Consumes: `/v1/tasks`, `/v1/tasks/{id}`, `/v1/tasks/{id}/events`, cancel/retry endpoints, health authentication state.
- Produces: task submission form, active-task polling, terminal verification display, cancel/retry actions, session-only API-token header.

- [ ] Add a failing component or browser regression test that asserts active tasks poll, terminal tasks stop polling, and docs load does not block overview data.
- [ ] Run the focused frontend test; expect failure because the operator panel and independent loaders are absent.
- [ ] Replace startup-wide data `Promise.all` with individual deduplicated loads; preserve explicit unavailable/error states per panel.
- [ ] Replace the prompt dialog with a form for task mode, timeout, budget, and acceptance checks.
- [ ] Render progress, verification, retry source, cancellation, and recovery state from the task API; store the optional bearer token only in `sessionStorage`.
- [ ] Run the focused frontend test and `npm run build`; expect pass.
- [ ] Commit the operator UI changes.

### Task 5: Full reliability verification and evidence handoff

**Files:**
- Modify: `README.md`, `BIG-PICTURE.md` markers only
- Test: full Python suite and frontend build

**Interfaces:**
- Consumes: all preceding contracts.
- Produces: updated operating instructions distinguishing local and production behavior.

- [ ] Write missing regression tests for any acceptance criteria not covered by Tasks 1–4.
- [ ] Run the entire `pytest -q` suite and `npm run build`; record actual counts and warnings.
- [ ] Run a real local Ollama task with an acceptance check, then cancel/retry a background task; verify ledger evidence and browser UI state.
- [ ] Document exact environment variables for local SQLite/Ollama and production PostgreSQL/token startup without writing secrets.
- [ ] Update only the managed markers in `BIG-PICTURE.md` with measured results and remaining deployment gaps.
- [ ] Commit documentation and verified tests.

## Self-review

- Spec coverage: all goals map to Tasks 1–4; Task 5 verifies and documents them. The deliberate non-goals remain excluded.
- Type consistency: Task 1 produces `verification`; Task 2 persists it; Task 3 exposes protected access; Task 4 renders it.
- Review Focus: each listed failure mode has a named test task.
- Proportion: five independently testable deliverables, ordered by their runtime dependency.
