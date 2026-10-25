from __future__ import annotations
import asyncio, hashlib, hmac, json, logging, re, time
from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from urllib.parse import parse_qs

from . import services
from .autofill import autofill
from .integrations import verify_slack
from .gateway import BudgetExceeded, ProviderError
from .memory_remote import RemoteMemory, RemoteMemoryError
from .scheduler import parse_cron
from .tasks import TaskLimit

log = logging.getLogger("tier1")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,40}$")


class RunReq(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    tier: str | None = None
    mode: str | None = None
    max_cost_usd: float | None = Field(default=None, gt=0, le=100)


class IngestReq(BaseModel):
    url: str | None = Field(default=None, max_length=2000)
    path: str | None = Field(default=None, max_length=300)
    name: str = Field(default="", max_length=200)


class BenchReq(BaseModel):
    tasks: list[str | dict]
    modes: list[str] = ["autopilot", "ralph", "team"]
    max_cost_usd: float | None = Field(default=None, gt=0, le=100)


class SourceReq(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=2_000_000)


class AskReq(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    k: int = Field(default=6, ge=1, le=12)
    save_to_vault: str | None = Field(default=None, max_length=300, description="vault dir in the sandbox; writes a cited note (needs TIER1_SANDBOX_WRITABLE=1)")


class StudioReq(BaseModel):
    kind: str
    focus: str = Field(default="", max_length=500)


class ChatReq(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    tier: str | None = None


class VaultReq(BaseModel):
    path: str = Field(default=".", max_length=300)


class AutofillReq(BaseModel):
    records: list[dict]
    fields: dict[str, str]


class JobReq(BaseModel):
    name: str
    kind: str = "cron"
    spec: str = ""
    prompt: str = Field(min_length=1, max_length=4000)
    enabled: bool = True


class MemReq(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    tags: str = ""


class GuardRepairReq(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


def create_app(svc: services.Services | None = None) -> FastAPI:
    svc = svc or services.build()
    s = svc.settings
    if s.env == "production" and (not s.api_token or not s.webhook_secret):
        raise RuntimeError("production requires TIER1_API_TOKEN and TIER1_WEBHOOK_SECRET")

    @asynccontextmanager
    async def lifespan(app):
        # runs left 'running' by a previous process can never finish: mark them so the UI/metrics stay truthful
        svc.store.x("UPDATE runs SET status='interrupted' WHERE status='running'")
        svc.scheduler.start()
        yield
        svc.scheduler.stop()

    app = FastAPI(title="Tier-1 Agent Engine", version="1.0.0", lifespan=lifespan)
    app.state.svc = svc
    buckets: dict[str, tuple[float, float]] = {}

    def auth(authorization: str = Header(default="")):
        if not s.api_token:
            return
        tok = authorization[7:] if authorization.lower().startswith("bearer ") else ""
        if not hmac.compare_digest(tok.encode(), s.api_token.encode()):
            raise HTTPException(401, "invalid or missing bearer token")

    def limit(request: Request):
        ip, now = (request.client.host if request.client else "?"), time.time()
        tokens, last = buckets.get(ip, (float(s.rate_limit_per_min), now))
        tokens = min(s.rate_limit_per_min, tokens + (now - last) * s.rate_limit_per_min / 60)
        if tokens < 1:
            raise HTTPException(429, "rate limit exceeded")
        buckets[ip] = (tokens - 1, now)

    def guard(fn):
        async def inner(*a, **k):
            try:
                return await fn(*a, **k)
            except ValueError as e:
                raise HTTPException(422, str(e))
            except BudgetExceeded as e:
                raise HTTPException(402, str(e))
            except ProviderError as e:
                raise HTTPException(502, f"provider error: {e}")
        return inner

    @app.get("/health")
    def health():
        return {"status": "ok", "provider": s.provider, "auth": "enabled" if s.api_token else "disabled",
                "skills": len(svc.skills.skills)}

    @app.get("/v1/guard/browser-repair", dependencies=[Depends(auth)])
    def guard_browser_repair(request: Request):
        """Run the integrated LAB guard in read-only mode; never claims browser proof."""
        lab_root = Path(__file__).resolve().parent.parent / "LAB"
        if str(lab_root.parent) not in sys.path:
            sys.path.insert(0, str(lab_root.parent))
        from LAB.tier1_guard_adapter import inspect_browser_repair
        result = inspect_browser_repair(lab_root.parent, request.url.port or 8000, "Tier-1 Control Plane")
        return {"status": result.status, "stopped_at": result.stopped_at, "reason": result.reason,
                "runtime_status": result.runtime_status, "scope_status": result.scope_status,
                "safety_status": result.safety_status, "impact_status": result.impact_status,
                "evidence_status": result.evidence_status, "evidence_level": "local-unavailable"}

    @app.post("/v1/guard/browser-repair", dependencies=[Depends(auth)])
    def guard_browser_repair_request(req: GuardRepairReq, request: Request):
        """Accept a real repair request while keeping the integrated path read-only."""
        lab_root = Path(__file__).resolve().parent.parent / "LAB"
        if str(lab_root.parent) not in sys.path:
            sys.path.insert(0, str(lab_root.parent))
        from LAB.tier1_guard_adapter import inspect_browser_repair
        result = inspect_browser_repair(lab_root.parent, request.url.port or 8000,
                                        "Tier-1 Control Plane", goal=req.prompt)
        return {"request": req.prompt, "status": result.status, "stopped_at": result.stopped_at,
                "reason": result.reason, "runtime_status": result.runtime_status,
                "scope_status": result.scope_status, "safety_status": result.safety_status,
                "impact_status": result.impact_status, "evidence_status": result.evidence_status,
                "evidence_level": "local-unavailable"}

    @app.get("/", include_in_schema=False)
    def ui():
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.post("/v1/run", dependencies=[Depends(auth), Depends(limit)])
    async def run(req: RunReq):
        return await guard(svc.modes.run)(req.prompt, mode=req.mode, tier=req.tier, trigger="api", max_cost_usd=req.max_cost_usd)

    @app.get("/v1/runs", dependencies=[Depends(auth)])
    def runs(limit: int = 50):
        return svc.store.runs_list(min(limit, 200))

    @app.get("/v1/runs/{run_id}", dependencies=[Depends(auth)])
    def run_get(run_id: str):
        r = svc.store.run_get(run_id)
        if not r:
            raise HTTPException(404, "run not found")
        return r

    @app.get("/v1/runs/{run_id}/capsule", dependencies=[Depends(auth)])
    def capsule(run_id: str):
        c = svc.store.capsule_get(run_id)
        if not c:
            raise HTTPException(404, "capsule not found")
        return c

    @app.get("/v1/skills", dependencies=[Depends(auth)])
    def skills():
        svc.skills.refresh()
        return {"skills": [{"name": k.name, "description": k.description, "triggers": k.triggers,
                            "priority": k.priority} for k in svc.skills.skills.values()],
                "errors": svc.skills.errors}

    @app.get("/v1/usage", dependencies=[Depends(auth)])
    def usage():
        return svc.store.usage_summary()

    @app.get("/v1/ledger", dependencies=[Depends(auth)])
    def ledger(run_id: str | None = None, limit: int = 100):
        return svc.store.ledger_list(run_id, min(limit, 500))

    @app.get("/v1/ledger/verify", dependencies=[Depends(auth)])
    def verify():
        return svc.store.ledger_verify()

    @app.get("/v1/memory", dependencies=[Depends(auth)])
    def mem_list():
        return svc.store.memory_list()

    @app.post("/v1/memory", dependencies=[Depends(auth)])
    def mem_add(m: MemReq):
        svc.store.memory_add(m.text, m.tags)
        return {"ok": True}

    @app.post("/v1/memory/codex-event", dependencies=[Depends(auth)])
    def memory_codex_event(payload: dict):
        try:
            return RemoteMemory(s).capture(payload)
        except RemoteMemoryError as e:
            raise HTTPException(503, str(e))

    @app.post("/v1/memory/search", dependencies=[Depends(auth)])
    def memory_search(payload: dict):
        query = str(payload.get("query", "")).strip()
        if not query:
            raise HTTPException(422, "query is required")
        if s.memory_url:
            try:
                return RemoteMemory(s).search(query)
            except RemoteMemoryError as e:
                raise HTTPException(503, str(e))
        return {"ok": True, "source": "local", "results": svc.store.memory_search(query, int(payload.get("k", 3)))}

    @app.get("/v1/jobs", dependencies=[Depends(auth)])
    def jobs():
        return svc.store.jobs_list()

    @app.post("/v1/jobs", dependencies=[Depends(auth)])
    def job_put(j: JobReq):
        if not NAME_RE.match(j.name) or j.kind not in ("cron", "webhook"):
            raise HTTPException(422, "invalid name or kind")
        if j.kind == "cron":
            try:
                parse_cron(j.spec)
            except ValueError as e:
                raise HTTPException(422, str(e))
        svc.store.job_put(j.name, j.kind, j.spec, j.prompt, j.enabled)
        return svc.store.job_get(j.name)

    @app.delete("/v1/jobs/{name}", dependencies=[Depends(auth)])
    def job_del(name: str):
        if not svc.store.job_delete(name):
            raise HTTPException(404, "job not found")
        return {"deleted": name}

    @app.post("/v1/jobs/{name}/fire", dependencies=[Depends(auth), Depends(limit)])
    async def job_fire(name: str):
        if not svc.store.job_get(name):
            raise HTTPException(404, "job not found")
        return await guard(svc.scheduler.fire)(name)

    @app.post("/v1/webhooks/{name}")
    async def webhook(name: str, request: Request, x_tier1_timestamp: str = Header(default=""),
                      x_tier1_signature: str = Header(default="")):
        """Signature = hex HMAC-SHA256(secret, f'{timestamp}.{raw_body}'); timestamp must be within 5 minutes."""
        if not s.webhook_secret:
            raise HTTPException(503, "webhook secret not configured")
        body = await request.body()
        try:
            fresh = abs(time.time() - float(x_tier1_timestamp)) <= 300
        except ValueError:
            fresh = False
        want = hmac.new(s.webhook_secret.encode(), f"{x_tier1_timestamp}.".encode() + body, hashlib.sha256).hexdigest()
        if not fresh or not hmac.compare_digest(want, x_tier1_signature):
            raise HTTPException(401, "bad signature or stale timestamp")
        rkey = "wh:" + want
        if svc.store.cache_get(rkey):
            raise HTTPException(409, "replayed webhook")
        svc.store.cache_put(rkey, "1", 600)
        job = svc.store.job_get(name)
        if not job or job["kind"] != "webhook" or not job["enabled"]:
            raise HTTPException(404, "no such enabled webhook job")
        extra = body.decode("utf-8", "replace")[:4000]
        extra = '<untrusted source="webhook">' + extra.replace("<", "&lt;") + "</untrusted>"
        return await guard(svc.scheduler.fire)(name, extra)

    # ---- notebooks (source-grounded Q&A, Obsidian vaults, session index)
    def sync(fn, *a, **k):
        try:
            return fn(*a, **k)
        except ValueError as e:
            raise HTTPException(422, str(e))
        except PermissionError as e:
            raise HTTPException(403, str(e))

    @app.get("/v1/kb", dependencies=[Depends(auth)])
    def kb_list():
        return svc.kb.notebooks()

    @app.post("/v1/kb/{nb}/sources", dependencies=[Depends(auth)])
    def kb_add(nb: str, r: SourceReq):
        return sync(svc.kb.index_text, nb, r.name, r.text, "note")

    @app.get("/v1/kb/{nb}/sources", dependencies=[Depends(auth)])
    def kb_sources(nb: str):
        return sync(svc.kb.sources, nb)

    @app.delete("/v1/kb/{nb}/sources", dependencies=[Depends(auth)])
    def kb_del(nb: str, name: str):
        if not sync(svc.kb.delete_source, nb, name):
            raise HTTPException(404, "source not found")
        return {"deleted": name}

    @app.get("/v1/kb/{nb}/search", dependencies=[Depends(auth)])
    def kb_search(nb: str, q: str, k: int = 6):
        return sync(svc.kb.search, nb, q, k)

    @app.get("/v1/kb/{nb}/backlinks", dependencies=[Depends(auth)])
    def kb_backlinks(nb: str, name: str):
        return sync(svc.kb.backlinks, nb, name)

    @app.post("/v1/kb/{nb}/import-vault", dependencies=[Depends(auth)])
    def kb_vault(nb: str, r: VaultReq):
        return sync(svc.kb.import_vault, r.path, nb)

    @app.post("/v1/kb/{nb}/ask", dependencies=[Depends(auth), Depends(limit)])
    async def kb_ask(nb: str, r: AskReq):
        res = await guard(svc.kb.ask)(svc.gateway, nb, r.question, r.k)
        if r.save_to_vault is not None and res["grounded"]:
            res["note"] = sync(svc.kb.save_note, r.save_to_vault, r.question[:100], res["answer"], res["run_id"],
                               [c["source"] for c in res["citations"]], nb if nb == "vault" else "")
        return res

    @app.post("/v1/kb/{nb}/ingest", dependencies=[Depends(auth), Depends(limit)])
    async def kb_ingest(nb: str, r: IngestReq):
        if bool(r.url) == bool(r.path):
            raise HTTPException(422, "provide exactly one of url or path")
        if r.url:
            try:
                return await svc.kb.ingest_url(svc.orch.tools, nb, r.url, r.name)
            except ValueError as e:
                raise HTTPException(422, str(e))
        return sync(svc.kb.ingest_file, nb, r.path, r.name)

    @app.post("/v1/bench", dependencies=[Depends(auth), Depends(limit)])
    async def bench_ep(r: BenchReq):
        from .bench import run_bench
        return await guard(run_bench)(svc, r.tasks, tuple(r.modes), r.max_cost_usd)

    @app.post("/v1/kb/{nb}/studio", dependencies=[Depends(auth), Depends(limit)])
    async def kb_studio(nb: str, r: StudioReq):
        return await guard(svc.kb.studio)(svc.gateway, nb, r.kind, r.focus)

    # ---- background tasks with live progress and cancellation
    @app.post("/v1/tasks", status_code=202, dependencies=[Depends(auth), Depends(limit)])
    async def task_start(req: RunReq):
        from .modes import parse_mode
        try:
            parse_mode(req.prompt, req.mode)
            if req.tier not in (None, "small", "medium", "large"):
                raise ValueError("tier must be small, medium or large")
            return {"task_id": svc.tasks.start(req.prompt, req.mode, req.tier, req.max_cost_usd), "status": "running"}
        except ValueError as e:
            raise HTTPException(422, str(e))
        except TaskLimit as e:
            raise HTTPException(429, str(e))

    def task_or_404(tid):
        r = svc.tasks.get(tid)
        if not r:
            raise HTTPException(404, "task not found (tasks are kept in memory; completed runs stay in /v1/runs)")
        return r

    @app.get("/v1/tasks/{tid}", dependencies=[Depends(auth)])
    def task_get(tid: str):
        return svc.tasks.public(task_or_404(tid))

    @app.delete("/v1/tasks/{tid}", dependencies=[Depends(auth)])
    def task_cancel(tid: str):
        task_or_404(tid)
        if not svc.tasks.cancel(tid):
            raise HTTPException(409, "task is not running")
        return {"cancelling": tid}

    @app.get("/v1/tasks/{tid}/events", dependencies=[Depends(auth)])
    async def task_events(tid: str):
        task_or_404(tid)

        async def gen():
            after, deadline = 0, time.time() + 900
            while time.time() < deadline:
                for e in svc.tasks.events_since(tid, after):
                    after = e["seq"]
                    yield "event: ledger\ndata: " + json.dumps({k: e[k] for k in ("seq", "run_id", "kind")}) + "\n\n"
                r = svc.tasks.get(tid)
                if r is None or r["status"] != "running":
                    for e in svc.tasks.events_since(tid, after):
                        yield "event: ledger\ndata: " + json.dumps({k: e[k] for k in ("seq", "run_id", "kind")}) + "\n\n"
                    yield "event: done\ndata: " + json.dumps({"status": r["status"] if r else "unknown"}) + "\n\n"
                    return
                await asyncio.sleep(0.25)
        return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    # ---- chat sessions
    @app.post("/v1/chat/{session}", dependencies=[Depends(auth), Depends(limit)])
    async def chat_send(session: str, r: ChatReq):
        return await guard(svc.chat.send)(session, r.message, r.tier, "chat")

    @app.get("/v1/chat/{session}", dependencies=[Depends(auth)])
    def chat_history(session: str):
        return sync(svc.chat.history, session)

    @app.delete("/v1/chat/{session}", dependencies=[Depends(auth)])
    def chat_delete(session: str):
        if not sync(svc.chat.delete, session):
            raise HTTPException(404, "session not found")
        return {"deleted": session}

    @app.post("/v1/autofill", dependencies=[Depends(auth), Depends(limit)])
    async def autofill_ep(r: AutofillReq):
        return await guard(autofill)(svc.gateway, svc.store, r.records, r.fields)

    # ---- Slack (slash command + app mentions), verified with Slack's signing scheme
    async def slack_body(request: Request, ts: str, sig: str) -> bytes:
        if not s.slack_signing_secret:
            raise HTTPException(503, "slack signing secret not configured")
        body = await request.body()
        if not verify_slack(s.slack_signing_secret, ts, body, sig):
            raise HTTPException(401, "bad slack signature or stale timestamp")
        if svc.store.cache_get("sl:" + sig):
            raise HTTPException(409, "replayed request")
        svc.store.cache_put("sl:" + sig, "1", 600)
        return body

    @app.post("/v1/slack/command", dependencies=[Depends(limit)])
    async def slack_command(request: Request, x_slack_request_timestamp: str = Header(default=""),
                            x_slack_signature: str = Header(default="")):
        body = await slack_body(request, x_slack_request_timestamp, x_slack_signature)
        return await svc.slack.command(parse_qs(body.decode("utf-8", "replace")))

    @app.post("/v1/slack/events", dependencies=[Depends(limit)])
    async def slack_events(request: Request, x_slack_request_timestamp: str = Header(default=""),
                           x_slack_signature: str = Header(default=""),
                           x_slack_retry_num: str = Header(default="")):
        body = await slack_body(request, x_slack_request_timestamp, x_slack_signature)
        try:
            payload = __import__("json").loads(body)
        except ValueError:
            raise HTTPException(422, "invalid JSON")
        return await svc.slack.event(payload if isinstance(payload, dict) else {}, x_slack_retry_num)

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics():
        u = svc.store.usage_summary()
        runs = svc.store.q("SELECT status, COUNT(*) n FROM runs GROUP BY status")
        lines = [f'tier1_runs_total{{status="{r["status"]}"}} {r["n"]}' for r in runs]
        lines += [f'tier1_tokens_total{{tier="{t["tier"]}",dir="in"}} {t["in_tok"] or 0}' for t in u["by_tier"]]
        lines += [f'tier1_tokens_total{{tier="{t["tier"]}",dir="out"}} {t["out_tok"] or 0}' for t in u["by_tier"]]
        lines += [f'tier1_cost_usd_total{{tier="{t["tier"]}"}} {t["cost"] or 0}' for t in u["by_tier"]]
        lines.append(f"tier1_spend_today_usd {u['spend_today_usd']}")
        lines.append(f"tier1_ledger_ok {1 if svc.store.ledger_verify()['ok'] else 0}")
        return "\n".join(lines) + "\n"

    @app.exception_handler(Exception)
    async def err(_, e):
        log.exception("unhandled")
        return JSONResponse({"detail": "internal error"}, status_code=500)

    return app
