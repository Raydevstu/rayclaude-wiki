# Top 10 Evaluation Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a repeatable, evidence-aware evaluation benchmark for the ten prioritized AI developer pain points without changing the existing `/v1/bench` contract.

**Architecture:** Add a small benchmark evaluator that owns a stable case manifest, invokes existing guard/evidence/benchmark primitives where possible, and serializes a report containing per-case status, evidence level, provenance, measurements, and unsupported claims. Keep browser and production checks opt-in and explicitly unavailable by default when no live session/resource is supplied.

**Tech Stack:** Python 3.10+, existing Tier-1 services and pytest suite, JSON/Markdown report output.

## File map

- Create `tier1/evaluation.py`: case definitions, result/report dataclasses, scoring, provenance validation, JSON/Markdown serialization, and runner entry point.
- Modify `tier1/cli.py`: add an `evaluate` command with manifest/output/provider options.
- Modify `tier1/api.py`: add a guarded `POST /v1/evaluate` endpoint that returns the same report shape without exposing secrets.
- Create `tests/test_evaluation.py`: unit tests for scoring, provenance, missing evidence, and serialization.
- Modify `tests/test_automation.py`: API contract coverage for the new endpoint.
- Modify `README.md`: document the command, evidence boundaries, and mock-provider caveat.
- Create `docs/superpowers/specs/2026-10-26-top-10-evaluation-benchmark-design.md`: approved design record.
- Create `docs/superpowers/plans/2026-10-26-top-10-evaluation-benchmark.md`: this plan.

## Review focus

- A result with HTTP 200 or compilation success alone cannot pass priority 1.
- Mock and cached evidence cannot be labeled as production or real.
- Missing browser/production inputs remain visible as `unavailable` or `unverified`.
- The report always contains all ten priorities, including failed or unavailable cases.
- Existing `/v1/bench` output and tests remain unchanged.

### Task 1: Establish the evaluation contract

**Files:** Create `tests/test_evaluation.py`; create `tier1/evaluation.py`.

- Write failing tests for ten stable priority IDs, result validation, score calculation, and report serialization.
- Run `python -m pytest tests/test_evaluation.py -q` and verify it fails because the evaluator does not exist.
- Implement the minimal dataclasses/functions: `CaseResult`, `EvaluationReport`, `evaluate_results`, `render_markdown`, and `run_evaluation` signatures.
- Add provenance rules that reject unsupported promotion of `mock`, `cached`, or `estimate` results to production proof.
- Run the focused tests and verify they pass.

### Task 2: Compose existing Tier-1 checks into the ten cases

**Files:** Modify `tier1/evaluation.py`; create/modify `LAB/test_evaluation_cases.py`.

- Write failing tests covering false-confidence, change accountability, context continuity, debugging loops, runtime identity, scope, maintainability, cost/performance, and evidence-ladder behavior.
- Run the focused LAB tests and verify the missing composition is exposed.
- Implement adapters that call existing guard modules and the existing `run_bench` function; keep each case's evidence level and provenance explicit.
- Add opt-in hooks for browser and production checks that return `unavailable` without a supplied live adapter.
- Run focused tests and verify all applicable local cases pass while unavailable gates remain labeled.

### Task 3: Add CLI and HTTP entry points

**Files:** Modify `tier1/cli.py`, `tier1/api.py`; modify `tests/test_automation.py`.

- Write failing tests for `tier1 evaluate` output and `POST /v1/evaluate`, including provider/caveat fields and validation errors.
- Run the focused tests and verify the interfaces are absent or incomplete.
- Implement the CLI and endpoint using the same evaluator and response schema; preserve authentication and request limits.
- Ensure reports contain no API key or secret values.
- Run focused API/CLI tests and verify JSON output is stable.

### Task 4: Document operation and evidence boundaries

**Files:** Modify `README.md`.

- Add the command examples for free mock evaluation and opt-in real-provider evaluation.
- Document that browser, persistence-restart, and production evidence are separate and may be unavailable locally.
- Document that benchmark costs and scores are synthetic under the mock provider.
- Run documentation-linked smoke commands and ensure the full test suite still passes.

### Task 5: Full verification and handoff

- Run `python -m pytest -q`.
- Run `python -m compileall -q tier1 LAB`.
- Run the evaluator with `TIER1_PROVIDER=mock` and save an output outside tracked source files.
- Confirm all ten priorities are present and inspect the report for correct provenance labels.
- Run `git diff --check` and `git status --short`.
- Report changed files, direct verification, evidence level, known gaps, and the exact next boundary.

## Traceability

- False confidence: Task 2 case plus Task 1 scoring rules.
- Change accountability: Task 2 guard adapter.
- Real-world testing: Task 2 browser/production unavailable gates.
- Context continuity: Task 2 context adapter.
- Debugging loops: Task 2 debugging adapter.
- Environment confusion: Task 2 runtime identity adapter.
- Scope control: Task 2 scope adapter.
- Maintainability: Task 2 maintainability adapter.
- Cost/performance: Task 2 existing benchmark adapter.
- Mock/stale/fabricated evidence: Task 1 provenance rules and Task 4 documentation.

## Execution note

Implement tasks in order because later adapters depend on the report contract. Do not add a dashboard or public share workflow in this slice.
