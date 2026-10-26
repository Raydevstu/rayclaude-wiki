"""Minimal MCP server over stdio (newline-delimited JSON-RPC 2.0). Logs go to stderr only."""
from __future__ import annotations
import asyncio, json, sys

from . import services
from .compiler import Compiler

TOOLS = [
    {"name": "tier1_run", "description": "Run a prompt through the Tier-1 pipeline (compile, skills, workers, audit).",
     "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"},
                     "tier": {"type": "string", "enum": ["small", "medium", "large"]},
                     "mode": {"type": "string", "enum": ["autopilot", "ralph", "team", "plan"]},
                     "max_cost_usd": {"type": "number"}}, "required": ["prompt"]}},
    {"name": "tier1_compile", "description": "Compile a raw prompt into a structured plan without executing it.",
     "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}},
    {"name": "tier1_kb_index", "description": "Index text into a notebook (FTS5) so it can be searched or asked about later.",
     "inputSchema": {"type": "object", "properties": {"notebook": {"type": "string"}, "name": {"type": "string"},
                     "text": {"type": "string"}}, "required": ["notebook", "name", "text"]}},
    {"name": "tier1_kb_search", "description": "BM25 search over a notebook; returns numbered source chunks.",
     "inputSchema": {"type": "object", "properties": {"notebook": {"type": "string"}, "query": {"type": "string"}},
                     "required": ["notebook", "query"]}},
    {"name": "tier1_kb_ask", "description": "Answer a question using only a notebook's sources, with verified citations.",
     "inputSchema": {"type": "object", "properties": {"notebook": {"type": "string"}, "question": {"type": "string"}},
                     "required": ["notebook", "question"]}},
    {"name": "tier1_kb_studio", "description": "Generate a cited briefing, faq, study_guide or timeline from a notebook.",
     "inputSchema": {"type": "object", "properties": {"notebook": {"type": "string"}, "kind": {"type": "string",
                     "enum": ["briefing", "faq", "study_guide", "timeline"]}, "focus": {"type": "string"}},
                     "required": ["notebook", "kind"]}},
    {"name": "tier1_chat", "description": "Send a message in a persistent chat session (remembers earlier turns).",
     "inputSchema": {"type": "object", "properties": {"session": {"type": "string"}, "message": {"type": "string"}},
                     "required": ["session", "message"]}},
    {"name": "tier1_skills", "description": "List registered skills.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "tier1_usage", "description": "Usage, cost and measured savings summary.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "tier1_verify_ledger", "description": "Verify the tamper-evident evidence ledger.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "memory_add", "description": "Store a Codex event in configured Ray/OARC memory or local memory.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}, "tags": {"type": "string"}}, "required": ["text"]}},
    {"name": "memory_search", "description": "Search configured memory.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "k": {"type": "integer"}}, "required": ["query"]}},
]


async def call_tool(svc, name: str, args: dict):
    if name == "tier1_run":
        r = await svc.modes.run(str(args.get("prompt", "")), mode=args.get("mode"), tier=args.get("tier"), trigger="mcp",
                                max_cost_usd=args.get("max_cost_usd"))
        return {k: r.get(k) for k in ("mode", "run_id", "status", "answer", "audit", "usage", "savings", "skills", "budget")}
    if name == "tier1_kb_studio":
        return await svc.kb.studio(svc.gateway, str(args.get("notebook", "")), str(args.get("kind", "")), str(args.get("focus", "")))
    if name == "tier1_chat":
        r = await svc.chat.send(str(args.get("session", "")), str(args.get("message", "")), trigger="mcp")
        return {k: r.get(k) for k in ("session", "mode", "run_id", "status", "answer", "usage")}
    if name == "tier1_kb_index":
        return svc.kb.index_text(str(args.get("notebook", "")), str(args.get("name", "")), str(args.get("text", "")))
    if name == "tier1_kb_search":
        return svc.kb.search(str(args.get("notebook", "")), str(args.get("query", "")))
    if name == "tier1_kb_ask":
        return await svc.kb.ask(svc.gateway, str(args.get("notebook", "")), str(args.get("question", "")))
    if name == "tier1_compile":
        return (await Compiler(svc.gateway).compile(str(args.get("prompt", "")))).to_dict()
    if name == "tier1_skills":
        svc.skills.refresh()
        return [{"name": s.name, "description": s.description} for s in svc.skills.skills.values()]
    if name == "tier1_usage":
        return svc.store.usage_summary()
    if name == "tier1_verify_ledger":
        return svc.store.ledger_verify()
    if name == "memory_add":
        return svc.memory.add(str(args.get("text", "")), str(args.get("tags", "")))
    if name == "memory_search":
        return svc.memory.search(str(args.get("query", "")), int(args.get("k", 3)))
    raise KeyError(name)


async def handle(svc, msg: dict):
    mid, method, params = msg.get("id"), msg.get("method", ""), msg.get("params") or {}
    if mid is None:        # notification
        return None
    ok = lambda r: {"jsonrpc": "2.0", "id": mid, "result": r}
    if method == "initialize":
        return ok({"protocolVersion": params.get("protocolVersion", "2024-11-05"),
                   "capabilities": {"tools": {}}, "serverInfo": {"name": "tier1-orchestrator", "version": "1.0.0"}})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        try:
            out = await call_tool(svc, params.get("name", ""), params.get("arguments") or {})
            return ok({"content": [{"type": "text", "text": json.dumps(out, default=str)}]})
        except KeyError:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "unknown tool"}}
        except Exception as e:
            return ok({"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True})
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found"}}


def serve():
    svc = services.build()

    async def main():
        loop = asyncio.get_running_loop()
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                return
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            reply = await handle(svc, msg)
            if reply is not None:
                sys.stdout.write(json.dumps(reply) + "\n")
                sys.stdout.flush()

    asyncio.run(main())
