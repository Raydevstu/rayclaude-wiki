# Rayclaude Wiki — Master Handoff

## Project identity — verify before answering or running anything

- **Product:** Tier-1 Control Plane (Rayclaude Wiki).
- **Active worktree:** `C:\Users\kafsh\.codex\worktrees\70c6\Rayclaude-wiki` on branch `codex/rayclaude-wiki`.
- **Do not infer the active project from broad Codex memories.** Earlier notes referencing `D:\Projects\Rayclaude-wiki`, LAB-only sandbox work, `hindsight-memory-slice`, or `Ray Sandbox OARC` are historical context, not the current task state.
- **UI:** React/Vite source is in `src/`, served locally on port `8001`; it is not the older static-only UI description.
- **API:** FastAPI on port `8000`; its live health contract identifies Ollama, PostgreSQL persistence, and development authentication state.

## Verified current state

- Reliability slice is implemented in the dirty worktree: deterministic acceptance checks, durable task/event lifecycle, cancellation/retry/restart recovery, bearer-token production guardrails, and the operator UI.
- The local API is running with Ollama and PostgreSQL. `/health` reported `status: ok`, `provider: ollama`, `persistence: postgres`, and `durable: true` during the 2026-10-26 review.
- Local PostgreSQL runs through Docker on host port `5433`.
- Tailscale private HTTPS routing is active at `https://ray.tail4663f6.ts.net/`; it proxies to the Vite UI and is tailnet-only. This is not public production deployment and API application authentication remains disabled in the local development environment.
- The Tier-1 MCP server is configured in `C:\Users\kafsh\.codex\config.toml` as `rayclaude-wiki`, with this worktree added to `PYTHONPATH` and the local Docker PostgreSQL URL on port `5433`.
- The active worktree is also marked `trusted` in the Codex project registry; the historical `D:\Projects\rayclaude-wiki` trust entry remains separate and non-authoritative.

## Critical continuity defect to fix next

New Codex chats can start without the prior transcript. The present MCP configuration is insufficient for durable project-scoped continuity:

1. The Tier-1 MCP tools were initially not exposed in the reviewing chat's available tool list. After restarting Codex, the live registry now exposes all 12 tools and a real recall has passed.
2. `tier1/mcp_server.py` previously sent `memory_add` and `memory_search` directly to its local SQLite store (`data/codex.db`), even though the running API uses PostgreSQL. The new adapter and MCP config now point both paths at the same local PostgreSQL database.
3. `TIER1_MEMORY_URL` is not configured, so `tier1/memory_remote.py` cannot capture to or recall from the scoped Ray/OARC memory service.
4. Broad Codex memory includes older project notes and supplied the wrong checkout, UI architecture, and next task when a fresh chat tried to continue.

The registry integration is now verified. This was not an Ollama, PostgreSQL, or Tailscale outage.

## Continuity slice implemented and directly verified

- Added `tier1/memory.py` as the shared API/MCP memory adapter with project identity, provenance, timestamp, source, and explicit available/failed/unavailable states.
- API and MCP memory calls now use the adapter; remote memory is selected only when configured, and remote failures do not silently fall back to another project.
- Added `tests/test_memory_adapter.py`: fresh-store recall passed, remote-unconfigured state is explicit, and remote failure is not mixed into local storage.
- Updated the local Codex MCP entry to use Docker PostgreSQL instead of the separate SQLite file.
- Direct MCP stdio proof passed on 2026-10-26: 12 tools listed; capture and recall both returned `status=available`, `source=postgres`, `project=Rayclaude-wiki`; recall returned the captured record; process exit `0`.
- `scripts/verify_codex_mcp.py` provides a repeatable, credential-safe server-side proof of config targeting, tool discovery, and PostgreSQL-backed recall.
- Fresh Codex desktop discovery is now directly verified after restart: this chat exposed all 12 `rayclaude-wiki` tools, and live `memory_add` followed by `memory_search` returned `status=available`, `source=postgres`, `project_id=Rayclaude-wiki`, with the captured record recalled.

## Exact next implementation boundary

1. Preserve this verified configuration and repeat the live discovery proof whenever the Codex config or worktree changes.
2. If a future fresh task does not expose the tools, diagnose the Codex registry/config reload boundary before claiming continuity.

## Boundaries and risks

- Preserve the existing dirty worktree. Do not reset, clean, overwrite, or stage unrelated generated data (`data/`, `sandbox/`, and `__pycache__/`).
- Do not expose memory records or credentials in logs, the UI, or the handoff.
- Automatic Codex capture and remote Ray/OARC integration remain unverified; only the fresh-chat MCP capture/recall path is verified.
- The configured MCP server uses the shared Docker PostgreSQL database; `TIER1_MEMORY_URL` remains optional and unset.
- The previous user instruction to commit, push, and prepare a release handoff is still pending. Only perform it after the intended source changes and documentation have been deliberately staged and verified.

## New-chat first action

Read this file and verify the active worktree, branch, MCP configuration, API health, and currently exposed Codex tools. `AGENTS.md` is not present in this worktree. Do not use generic memory notes as project truth.
