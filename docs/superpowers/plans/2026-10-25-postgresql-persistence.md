# PostgreSQL Durable Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a PostgreSQL-backed durable store for production while preserving SQLite for local development and free staging.

**Architecture:** Select the backend from `TIER1_DATABASE_URL`; keep the current SQLite store as the default and introduce a PostgreSQL implementation with the same public `Store` methods. Use one shared logical schema and explicit startup validation so production fails closed when the database is unavailable or misconfigured.

**Tech Stack:** Python 3.10+, FastAPI, SQLite, PostgreSQL, psycopg 3, pytest, Render Blueprint YAML.

**Spec:** `PDR-DOC/MASTER-HANDOFF.md` current boundary and the approved user request to add PostgreSQL persistence while preserving SQLite compatibility.

## Global Constraints

- SQLite remains the default when `TIER1_DATABASE_URL` is absent.
- Render production uses the internal PostgreSQL connection string through `TIER1_DATABASE_URL`.
- No database credentials are committed to the repository.
- Writes and rollback remain governed and disabled by default.
- Free Render staging remains supported but is not durable.

## Review Focus

- A missing database URL must continue to use SQLite; test backend selection.
- A PostgreSQL URL must not silently fall back to SQLite; test explicit configuration failure.
- JSON payloads and timestamps must round-trip identically across stores; test representative durable records.
- Startup schema creation must be repeatable; test idempotent initialization.
- Render configuration must wire the database URL without embedding secrets; test YAML structure and secret references.

### Task 1: Store backend boundary

**Files:**
- Create: `tier1/postgres_store.py`
- Modify: `tier1/store.py`
- Modify: `tier1/config.py`
- Modify: `tier1/services.py`
- Test: `LAB/test_store_backends.py`

**Interfaces:**
- Consumes: existing `Store` methods used by services and lifecycle jobs.
- Produces: `build_store(database_url: str | None, sqlite_path: str) -> Store` and a PostgreSQL implementation with the existing store contract.

- [ ] Write failing tests for SQLite default selection, PostgreSQL selection, explicit connection errors, and schema idempotence.
- [ ] Run `python -m pytest LAB/test_store_backends.py -q` and verify the new behavior fails before implementation.
- [ ] Implement the backend selector and PostgreSQL store using parameterized queries and the existing method names.
- [ ] Run the focused backend tests and verify they pass.
- [ ] Run the existing store/core tests and verify SQLite behavior is unchanged.
- [ ] Commit as `feat: add durable postgres store`.

### Task 2: Render production wiring

**Files:**
- Create: `render.yaml`
- Modify: `Dockerfile`
- Modify: `README.md`
- Test: `LAB/test_render_config.py`

**Interfaces:**
- Consumes: `TIER1_DATABASE_URL` from the Render database connection string.
- Produces: a Render Blueprint declaring the web service and a managed PostgreSQL resource, with the service receiving the connection string through `fromDatabase`.

- [ ] Write failing configuration tests for service/database declarations, internal connection wiring, and absence of literal credentials.
- [ ] Run the focused configuration test and verify it fails before the Blueprint exists.
- [ ] Add the Blueprint and install the PostgreSQL runtime dependency in the image build.
- [ ] Document that applying the Blueprint creates a billable managed database and that free staging remains SQLite.
- [ ] Run configuration validation and the focused tests.
- [ ] Commit as `feat: wire render durable persistence`.

### Task 3: Full verification and handoff

**Files:**
- Modify: `PDR-DOC/MASTER-HANDOFF.md`

- [ ] Run `python -m pytest -q` and record all failures, including unrelated Windows subprocess failures.
- [ ] Run `python -m compileall -q tier1 LAB`.
- [ ] Verify the public staging URL still returns HTTP 200; do not claim PostgreSQL production proof until a user applies the Blueprint and supplies the database resource.
- [ ] Update the handoff with changed files, test evidence, deployment boundary, and the exact next user action.
- [ ] Commit and push the verified branch and `main`.

