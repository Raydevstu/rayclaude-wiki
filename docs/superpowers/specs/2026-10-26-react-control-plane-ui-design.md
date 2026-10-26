# React Control Plane UI Design

## Intent

Modernize the Tier-1 Control Plane from its current single-file static frontend into a maintainable React workspace for AI developers and vibe coders. The new interface should feel like a professional developer product: dense but readable, evidence-aware, responsive, and visually consistent with the supplied NexaCRM and tweakcn references.

## Goals

- Preserve the existing FastAPI routes, storage, benchmark behavior, and mock-provider workflow.
- Replace the static HTML presentation with a React and TypeScript frontend.
- Provide a persistent left navigation, top command bar, central workspace, and optional evidence panel.
- Add live API-backed cards, tables, charts, loading states, empty states, and failure states.
- Show provenance for every metric: real, mock, cached, estimated, unavailable, or unverified.
- Support dark, light, and system themes with configurable radius, density, scale, and sidebar mode.
- Keep the application usable at the existing local port and inside Docker.

## Non-goals

- No FastAPI rewrite.
- No provider credential handling in the frontend.
- No fabricated production metrics.
- No direct copying of reference template code or assets.
- No dependency on paid dashboard services.

## Approaches

1. Incrementally extend the existing HTML. This has the lowest migration risk but cannot provide a strong component system or long-term maintainability.
2. Build a React/Vite frontend against the existing FastAPI API. This preserves backend behavior while enabling shadcn/ui composition, a real theme system, and charting. This is the selected approach.
3. Rewrite the frontend and backend together. This creates unnecessary risk and makes evidence boundaries harder to preserve.

## Selected technology

- React, TypeScript, and Vite.
- Tailwind CSS with shadcn/ui source components and Radix primitives.
- Lucide icons, subject to the actual shadcn project configuration.
- Recharts for API-backed charts.
- TanStack Query for server state, loading, retry, and stale states.
- Geist or Manrope typography, subject to the selected theme configuration.
- Docker for repeatable local and staging execution.

## Information architecture

- Overview: operational summary, recent runs, benchmark score, and evidence health.
- Run task: prompt, mode, tier, execution status, answer, changes, and verification.
- Runs: searchable run history and task capsules.
- Benchmarks: Top 10 evaluation and local performance comparisons.
- Evidence: provenance and verification matrix.
- Usage & cost: calls, tokens, cost, latency, retries, provider, and model.
- Skills, Jobs, Docs & FAQ, and Settings: existing capabilities in the new shell.

## Visual system

Use a neutral dark-first surface system inspired by the supplied NexaCRM references, with restrained blue, purple, teal, orange, and pink accents for categories and status. Cards use semantic tokens, thin borders, consistent medium radius, and compact spacing. Color is never the only status signal. Charts must include labels, legends, empty states, and provenance badges.

## Delivery slices

1. Frontend shell, theme tokens, navigation, responsive layout, and API client.
2. Overview and Run task workspace using existing endpoints.
3. Runs, Evidence, Usage, and Top 10 benchmark dashboards.
4. Docs, settings, accessibility, browser verification, and Docker parity.

## Acceptance gates

- Existing backend tests remain green.
- The frontend builds without TypeScript errors.
- Overview and Run task operate against the live local API.
- Loading, empty, unauthorized, unavailable, mock, and error states are visible and truthful.
- Charts render only from API responses and label synthetic/mock data.
- Browser verification covers the main run journey and navigation.
- Docker serves the same app and API contract locally.
