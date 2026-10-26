# React Control Plane UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a React/Vite frontend foundation that serves the existing Tier-1 Control Plane API with a professional developer-workspace shell.

**Architecture:** Keep FastAPI as the backend and replace only the static presentation with a Vite-built React application. The first slice provides a typed API client, theme-aware shell, left navigation, overview cards, and truthful loading/error/empty states. Later slices can add the full run, evidence, usage, and benchmark pages against the same shell.

**Tech Stack:** React, TypeScript, Vite, Tailwind CSS, shadcn/ui source components, Radix primitives, Lucide icons, TanStack Query, and Recharts where dependencies are justified by the existing API.

**Spec:** `docs/superpowers/specs/2026-10-26-react-control-plane-ui-design.md`

## Global Constraints

- Preserve the existing FastAPI routes, storage, benchmark behavior, and mock-provider workflow.
- Do not fabricate production metrics.
- Charts must label mock, cached, estimated, unavailable, and unverified data.
- Do not copy reference template code or assets directly.
- Keep the app usable at local port `8001` and inside Docker.

## Review Focus

- API unavailable: shell remains usable and shows an explicit connection error.
- Empty or partial API responses: cards show no-data states rather than zeros presented as facts.
- Mock provider: provider and evidence badges remain visible.
- Narrow viewport: navigation and cards remain usable without horizontal overflow.
- Theme changes: contrast and semantic status colors remain readable in light and dark modes.

### Task 1: Frontend project foundation

**Files:**
- Create: `package.json`, `index.html`, `tsconfig.json`, `tsconfig.node.json`, `vite.config.ts`
- Create: `src/main.tsx`, `src/app.tsx`, `src/index.css`, `src/lib/api.ts`, `src/lib/types.ts`
- Modify: `tier1/static/index.html` only after the Vite build contract is established

**Interfaces:**
- Produces `npm run build` and `npm run dev` scripts.
- Produces `apiGet<T>(path: string): Promise<T>` and shared response types for the shell.

- [ ] Add package and TypeScript/Vite configuration with React and Tailwind-compatible CSS entry points.
- [ ] Add a failing build smoke test or equivalent compile check for the new entrypoint.
- [ ] Run the build check and confirm it fails before dependencies and source exist.
- [ ] Implement the minimal app entrypoint and API client with same-origin requests.
- [ ] Run `npm install` and `npm run build`; expected: successful production build.

### Task 2: Professional workspace shell

**Files:**
- Create: `src/components/app-shell.tsx`, `src/components/sidebar.tsx`, `src/components/topbar.tsx`, `src/components/ui/status-badge.tsx`
- Modify: `src/app.tsx`, `src/index.css`

**Interfaces:**
- Consumes the API client and theme tokens from Task 1.
- Produces a responsive shell with selected navigation state and explicit evidence/status styling.

- [ ] Add a render smoke check for navigation labels and the Overview heading.
- [ ] Run the check before implementation and observe the expected missing-component failure.
- [ ] Implement the shell using semantic layout regions, accessible buttons, and token-based colors.
- [ ] Add dark/light/system theme state without hardcoding reference-template colors into individual components.
- [ ] Run the frontend build and the render smoke check; expected: both pass.

### Task 3: Overview foundation and backend handoff

**Files:**
- Create: `src/features/overview/overview-page.tsx`, `src/features/overview/metric-card.tsx`, `src/features/overview/data-state.tsx`
- Modify: `src/app.tsx`, `tier1/static/index.html` or backend static serving configuration as required by the build output

**Interfaces:**
- Consumes `apiGet` and typed API responses from Task 1.
- Produces overview cards for run count, benchmark score, provider, and evidence state without inventing missing values.

- [ ] Add render tests for real values, unavailable values, and mock-provider labeling.
- [ ] Run them before implementation and confirm the expected failure.
- [ ] Implement the Overview page with cards, recent activity placeholder, and explicit unavailable state.
- [ ] Connect the built frontend to the existing FastAPI static route without changing API behavior.
- [ ] Run frontend build, focused render tests, and the existing Python suite.

### Task 4: Verification and Docker parity

**Files:**
- Create or modify: `Dockerfile`, `docker-compose.yml`, `README.md`

- [ ] Build the frontend and container image locally.
- [ ] Start the container with the existing mock provider and local-safe configuration.
- [ ] Verify the browser page title, shell identity, API connection state, and port binding.
- [ ] Run the existing Python tests and record the exact result.

