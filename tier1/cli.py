from __future__ import annotations
import argparse, asyncio, json, sys

from . import services


def _print(o):
    print(json.dumps(o, indent=2, default=str))


def main(argv=None):
    p = argparse.ArgumentParser(prog="tier1", description="Tier-1 agent engine")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a prompt through the pipeline")
    r.add_argument("prompt")
    r.add_argument("--tier", choices=["small", "medium", "large"])
    r.add_argument("--json", action="store_true", help="print the full result")
    r.add_argument("--max-cost", type=float, help="soft per-request spend cap in USD")
    r.add_argument("--mode", choices=["autopilot", "ralph", "team", "plan"], help="execution mode (or prefix 'ralph:' etc.)")
    c = sub.add_parser("compile", help="compile a prompt without executing it")
    c.add_argument("prompt")
    sv = sub.add_parser("serve", help="start the HTTP API, scheduler and control-plane UI")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sub.add_parser("mcp", help="run as an MCP server on stdio")
    sub.add_parser("skills", help="list skills")
    sub.add_parser("usage", help="usage, cost and measured savings")
    led = sub.add_parser("ledger", help="evidence ledger")
    led.add_argument("action", choices=["verify", "tail"])
    j = sub.add_parser("jobs", help="manage cron/webhook jobs")
    j.add_argument("action", choices=["list", "add", "remove", "fire"])
    j.add_argument("--name")
    j.add_argument("--kind", choices=["cron", "webhook"], default="cron")
    j.add_argument("--spec", default="")
    j.add_argument("--prompt", default="")
    k = sub.add_parser("kb", help="notebooks: grounded Q&A over indexed sources and Obsidian vaults")
    k.add_argument("action", choices=["list", "add", "search", "ask", "studio", "ingest", "import-vault", "backlinks"])
    k.add_argument("--notebook", default="default")
    k.add_argument("--name", default="")
    k.add_argument("--file", default="", help="file (inside the sandbox) to index")
    k.add_argument("text", nargs="?", default="", help="text/query/question/vault path (or use --text)")
    k.add_argument("--text", dest="text_opt", default="", help="same as the positional; use when options precede it")
    bn = sub.add_parser("bench", help="compare execution modes on your own tasks (JSON list of prompts in the sandbox)")
    bn.add_argument("tasks")
    bn.add_argument("--modes", default="autopilot,ralph,team")
    bn.add_argument("--max-cost", type=float)
    ch = sub.add_parser("chat", help="send a message in a persistent chat session")
    ch.add_argument("session")
    ch.add_argument("message")
    af = sub.add_parser("autofill", help="fill columns for records: --records file.json --field name=instruction ...")
    af.add_argument("--records", required=True, help="JSON file containing a list of objects")
    af.add_argument("--field", action="append", default=[], help="column=instruction (use a|b|c for enums)")
    m = sub.add_parser("memory", help="long-term memory")
    m.add_argument("action", choices=["add", "list"])
    m.add_argument("text", nargs="?", default="")
    a = p.parse_args(argv)

    if a.cmd == "mcp":
        from .mcp_server import serve
        return serve()
    if a.cmd == "serve":
        import uvicorn
        from .api import create_app
        return uvicorn.run(create_app(), host=a.host, port=a.port, log_level="info")

    svc = services.build()
    try:
        if a.cmd == "run":
            res = asyncio.run(svc.modes.run(a.prompt, mode=a.mode, tier=a.tier, trigger="cli", max_cost_usd=a.max_cost))
            if a.json:
                _print(res)
            else:
                print(res["answer"])
                sv, au = res.get("savings", {}), res.get("audit", {})
                print(f"\n[{res['status']}] mode={res['mode']} run={res['run_id']} cost=${res['usage']['cost_usd']:.5f} "
                      f"saved={sv.get('saved_pct')}% audit={au.get('score')}", file=sys.stderr)
        elif a.cmd == "compile":
            from .compiler import Compiler
            _print(asyncio.run(Compiler(svc.gateway).compile(a.prompt)).to_dict())
        elif a.cmd == "skills":
            _print([{"name": s.name, "description": s.description} for s in svc.skills.skills.values()])
        elif a.cmd == "usage":
            _print(svc.store.usage_summary())
        elif a.cmd == "ledger":
            _print(svc.store.ledger_verify() if a.action == "verify" else svc.store.ledger_list(limit=20))
        elif a.cmd == "kb":
            a.text = a.text_opt or a.text
            if a.action == "list":
                _print(svc.kb.notebooks())
            elif a.action == "add":
                text = a.text
                if a.file:
                    from .safety import safe_path
                    text = safe_path(svc.settings.sandbox_dir, a.file).read_text(errors="replace")
                _print(svc.kb.index_text(a.notebook, a.name or a.file or "note", text))
            elif a.action == "search":
                _print(svc.kb.search(a.notebook, a.text))
            elif a.action == "ask":
                _print(asyncio.run(svc.kb.ask(svc.gateway, a.notebook, a.text)))
            elif a.action == "ingest":
                if a.text.startswith(("http://", "https://")):
                    _print(asyncio.run(svc.kb.ingest_url(svc.orch.tools, a.notebook, a.text, a.name)))
                else:
                    _print(svc.kb.ingest_file(a.notebook, a.text, a.name))
            elif a.action == "studio":
                kind, _, focus = a.text.partition(" ")
                _print(asyncio.run(svc.kb.studio(svc.gateway, a.notebook, kind, focus)))
            elif a.action == "import-vault":
                _print(svc.kb.import_vault(a.text or ".", a.notebook))
            else:
                _print(svc.kb.backlinks(a.notebook, a.name))
        elif a.cmd == "bench":
            from .bench import run_bench
            from .safety import safe_path
            tasks = json.loads(safe_path(svc.settings.sandbox_dir, a.tasks).read_text())
            _print(asyncio.run(run_bench(svc, tasks, tuple(a.modes.split(",")), a.max_cost)))
        elif a.cmd == "chat":
            print(asyncio.run(svc.chat.send(a.session, a.message, trigger="cli"))["answer"])
        elif a.cmd == "autofill":
            from .autofill import autofill
            from .safety import safe_path
            recs = json.loads(safe_path(svc.settings.sandbox_dir, a.records).read_text())
            fields = dict(f.split("=", 1) for f in a.field)
            _print(asyncio.run(autofill(svc.gateway, svc.store, recs, fields)))
        elif a.cmd == "memory":
            if a.action == "add":
                svc.store.memory_add(a.text)
            _print(svc.store.memory_list())
        elif a.cmd == "jobs":
            from .scheduler import parse_cron
            if a.action == "list":
                _print(svc.store.jobs_list())
            elif a.action == "add":
                if a.kind == "cron":
                    parse_cron(a.spec)
                svc.store.job_put(a.name, a.kind, a.spec, a.prompt)
                _print(svc.store.job_get(a.name))
            elif a.action == "remove":
                _print({"deleted": svc.store.job_delete(a.name)})
            else:
                _print(asyncio.run(svc.scheduler.fire(a.name)))
    except Exception as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
