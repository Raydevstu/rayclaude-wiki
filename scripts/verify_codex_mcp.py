"""Verify Codex MCP configuration, tool discovery, and scoped memory recall.

This proves the server-side contract only. Codex desktop must be restarted or
refreshed separately before its live tool registry can be claimed as verified.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path(os.environ.get("CODEX_CONFIG", Path.home() / ".codex" / "config.toml"))


def exchange(proc: subprocess.Popen[str], message: dict) -> dict:
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("MCP server exited before replying")
    return json.loads(line)


def main() -> int:
    config_text = CONFIG.read_text(encoding="utf-8")
    if "[mcp_servers.rayclaude-wiki]" not in config_text:
        raise RuntimeError(f"missing rayclaude-wiki MCP entry in {CONFIG}")
    if str(ROOT).lower() not in config_text.lower():
        raise RuntimeError("MCP config does not point at the active worktree")

    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(ROOT),
        "TIER1_DATABASE_URL": os.environ.get(
            "TIER1_DATABASE_URL",
            "postgresql://tier1:tier1-local-only@127.0.0.1:5433/tier1",
        ),
        "TIER1_PROVIDER": os.environ.get("TIER1_PROVIDER", "mock"),
        "TIER1_SKILLS_DIR": str(ROOT / "skills"),
    })
    proc = subprocess.Popen(
        [sys.executable, "-m", "tier1", "mcp"], cwd=ROOT, env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    try:
        exchange(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        listed = exchange(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names = {tool["name"] for tool in listed["result"]["tools"]}
        required = {"memory_add", "memory_search"}
        if missing := required - names:
            raise RuntimeError(f"MCP tool list is missing: {sorted(missing)}")

        token = f"codex-mcp-proof-{uuid.uuid4()}"
        added = exchange(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                "params": {"name": "memory_add", "arguments": {"text": token, "tags": "verification"}}})
        searched = exchange(proc, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                   "params": {"name": "memory_search", "arguments": {"query": token, "k": 3}}})
        searched_text = searched["result"]["content"][0]["text"]
        recalled = token in searched_text
        print(json.dumps({"tools": len(names), "add_status": added["result"]["content"][0]["text"], "recalled": recalled}))
        return 0 if recalled else 1
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
