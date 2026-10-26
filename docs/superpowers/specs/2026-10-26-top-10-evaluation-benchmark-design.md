# Top 10 AI Developer Evaluation Benchmark

## Intent

Create a repeatable evaluation for the ten prioritized pain points supplied by
the user. The benchmark is for AI developers and vibe coders evaluating whether
Tier-1 produces trustworthy engineering outcomes, not merely successful HTTP
responses. It must preserve evidence provenance and make unsupported claims
visible.

## Goals

- Evaluate all ten priorities with stable, named benchmark cases.
- Produce machine-readable JSON and a concise Markdown report.
- Record status, evidence level, provenance, timestamps, changed files, and
  measurements such as latency, calls, retries, cost, and provider.
- Distinguish `real`, `mock`, `cached`, `estimate`, `unavailable`, `not_run`,
  `failed`, and `unverified` evidence.
- Reuse existing benchmark, guard, evidence, and usage infrastructure.
- Make the suite runnable locally with the free mock provider and optionally
  against a configured real provider without exposing secrets.

## Non-goals

- Do not claim production readiness from local or mock evidence.
- Do not add a public sharing feature, browser automation framework, or paid
  hosting resource as part of this benchmark.
- Do not rewrite the existing `/v1/bench` contract.
- Do not treat compilation, HTTP 200, synthetic scores, or cached results as
  full user-journey proof.

## Anti-goals

- No fabricated scores for unavailable evidence.
- No hidden network calls or provider credentials in tests.
- No broad refactor of the existing control plane.
- No benchmark result that silently mixes cached and uncached runs.

## Approaches considered

1. **Report-only assessment.** Run existing checks and manually summarize the
   ten areas. This is quick but not repeatable and will regress silently.
2. **Repeatable benchmark suite (selected).** Add a manifest-driven evaluator
   that runs focused probes for each priority, reuses current `/v1/bench` and
   guard contracts, and emits JSON plus Markdown. This gives the strongest
   value with the smallest product change.
3. **Suite plus dashboard.** Add the evaluator and a UI tab for history. This
   improves visibility but expands the scope before the scoring/evidence
   contract has proved stable.

The selected approach is option 2 because the current app already exposes
benchmark and evidence primitives, while the missing capability is a single
truthful evaluation boundary. A dashboard can consume the JSON later.

## Evaluation model

Each priority has one or more cases. A case returns:

```json
{
  "id": "false-confidence.http-200-is-not-done",
  "priority": 1,
  "status": "passed|failed|unavailable|not_run|unverified",
  "evidence_level": "code|api|browser|journey|persistence|error_state|benchmark|production",
  "provenance": "real|mock|cached|estimate|unavailable",
  "measurements": {},
  "details": "...",
  "timestamp": "..."
}
```

The overall score is the percentage of cases with `passed`; unavailable and
unverified cases remain visible and do not become passing zeros. The report
also includes coverage by priority, evidence-level coverage, and a list of
claims that remain unsupported.

## Priority coverage

1. False confidence: require a distinction between compile/API success and a
   completed user journey, including a deliberately insufficient HTTP-200 case.
2. Unclear changes and side effects: inspect the governed change record for
   changed files, ownership, risk, and rollback evidence.
3. Weak real-world testing: run API and browser/journey checks where available;
   label browser coverage unavailable rather than inferring it from API checks.
4. Lost project context: verify context/decision persistence and retrieval.
5. Debugging loops: verify failed attempts and prior approaches are recorded and
   repeated approaches are detectable.
6. Environment and launch confusion: verify runtime identity, health, port,
   database/provider, and process diagnostics agree.
7. Over-scoped AI changes: verify scope guard rejects unrelated changed files.
8. Poor maintainability: verify maintainability guard checks structure, tests,
   documentation, and reasoning artifacts.
9. Invisible cost and performance: run the existing mode benchmark and record
   provider, calls, tokens, cost, latency, retries, and cache state.
10. Mock, stale, or fabricated evidence: verify provenance labels and that mock,
    cached, unavailable, and production claims cannot be promoted silently.

## Constraints and safety

- Default execution uses `TIER1_PROVIDER=mock` and is free and deterministic.
- Real-provider execution is opt-in through environment configuration; secrets
  are read but never printed or persisted in report content.
- Browser and production evidence are separate gates from local code/API tests.
- Existing tests remain authoritative for individual guard behavior; the new
  suite composes them and adds only the missing evaluation contract.
- Generated benchmark outputs belong in an ignored output directory or an
  explicitly selected artifact path, not in the source tree by default.

## Acceptance criteria

- A single command runs all ten priorities and exits nonzero if an applicable
  case fails.
- The command emits JSON and Markdown with all ten priorities represented.
- Every result includes status, evidence level, provenance, and timestamp.
- Mock runs clearly state that costs/scores are synthetic.
- Cached or unavailable cases are explicitly labeled and never reported as
  production proof.
- Existing tests and `/v1/bench` behavior remain unchanged.
- A focused test suite covers scoring, provenance, missing evidence, and report
  serialization, followed by the full project suite.

## Open implementation boundary

The implementation plan should decide the exact command name, manifest location,
and whether the first version invokes browser checks through an existing local
browser session or reports browser coverage as unavailable when no session is
provided. The default must remain deterministic and runnable without a browser.
