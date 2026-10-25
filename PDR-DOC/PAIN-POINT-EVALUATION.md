# AI-Assisted App Building: Pain-Point Evaluation

## Purpose

This document records the main pain points users experience when using AI to build, modify, test, and launch applications.

## Common pain points

1. **Over-scoped changes** — AI changes too many files when the user needs a small, targeted fix.
2. **False confidence** — Code may look polished while failing in real user workflows.
3. **Lost project context** — Decisions, files, previous errors, and requirements are forgotten between conversations.
4. **Unreliable completion claims** — AI may claim success after only compiling, starting a process, or receiving HTTP 200.
5. **Debugging loops** — Each attempted fix can introduce a different failure, making progress difficult to track.
6. **Environment friction** — Dependencies, environment variables, ports, runtimes, and database setup are often unclear.
7. **Unclear change impact** — Users do not know which files changed or what existing behavior may break.
8. **Weak end-to-end validation** — Unit tests can pass while the browser experience or production flow remains broken.
9. **Poor maintainability** — Generated code may work but lack clear architecture, rationale, tests, or documentation.
10. **Invisible operational cost** — Token usage, provider cost, latency, retries, and model quality are often hidden.
11. **Repeated explanation** — Users must repeatedly restate the same project context and goals.
12. **Stale or synthetic evidence** — AI may rely on mock data, cached state, stale processes, or the wrong app instance.

## Prioritized Top 10 for AI Developers and Vibe Coders

These are the highest-priority versions of the common pain points for a normal developer using AI to build an application.

1. **False confidence** — The app says “done” when it only compiled or returned HTTP 200. This is the most dangerous problem.
2. **Unclear changes and side effects** — Users need to know exactly which files changed and what may have broken.
3. **Weak real-world testing** — Unit tests are not enough; the actual browser flow and important user journeys must be tested.
4. **Lost project context** — Requirements, decisions, previous errors, and architecture should persist across conversations.
5. **Debugging loops** — The system should track attempted fixes and avoid repeating failed approaches.
6. **Environment and launch confusion** — It should identify the correct project, port, database, process, dependencies, and runtime.
7. **Over-scoped AI changes** — AI should make the smallest safe change instead of rewriting unrelated parts of the app.
8. **Poor maintainability** — Generated code needs structure, tests, documentation, and clear reasoning, not just immediate functionality.
9. **Invisible cost and performance** — Users should see token usage, cost, latency, retries, and which model performed the work.
10. **Mock, stale, or fabricated evidence** — The system must distinguish real data, mock data, cached results, estimates, and unverified claims.

### Prioritization note

These Top 10 are not additional pain points. They are the most important, product-focused versions of the original 12 common pain points. Several original items are combined under broader themes such as project context, maintainability, operational cost, and evidence quality.

## Primary user problem

The central pain point is not that AI cannot write code. It is that users cannot reliably tell whether the result is correct, complete, and safe to use.

## Evaluation criteria

An AI app-building workflow should make these questions easy to answer:

- What changed?
- What was tested?
- What was not tested?
- Which application and runtime were actually launched?
- Were the results based on real data, mock data, or estimates?
- What remains incomplete or risky?
- What is the exact next action?

## Product implication

The strongest AI app-building experience should optimize for confidence, not only code generation. It should provide evidence-backed status such as **complete**, **partial**, **blocked**, or **not verified**, and keep implementation evidence separate from browser, benchmark, and production evidence.

## Tier-1 opportunity

Tier-1 can address these pain points by combining prompt compilation, controlled execution modes, memory and tool workers, usage accounting, audit scoring, ledger evidence, and truthful launch verification in one workflow.

Its most important promise should be:

> The system does not merely generate an app; it shows what happened, what was proven, and what still needs attention.
