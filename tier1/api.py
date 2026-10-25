from __future__ import annotations
import asyncio, hashlib, hmac, json, logging, os, re, time, uuid
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


class GuardWriteReq(BaseModel):
    approval_id: str = Field(min_length=1, max_length=100)
    sandbox_id: str | None = Field(default=None, min_length=1, max_length=100)
    approved: bool = False
    branch: str = Field(min_length=1, max_length=200)
    commit: str = Field(min_length=1, max_length=200)
    files: dict[str, str]
    ai_files: list[str]
    protected_user_files: list[str] = []
    baseline_digests: dict[str, str]
    agent_run_id: str | None = None


class GuardApprovalReq(BaseModel):
    goal: str = Field(min_length=1, max_length=4000)
    branch: str = Field(min_length=1, max_length=200)
    commit: str = Field(min_length=1, max_length=200)
    files: dict[str, str]
    ai_files: list[str]
    protected_user_files: list[str] = []
    baseline_digests: dict[str, str]
    agent_run_id: str | None = None
    sandbox_id: str | None = Field(default=None, min_length=1, max_length=100)


class GuardAgentReq(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    tier: str | None = None


class GuardRollbackReq(BaseModel):
    approved: bool = False


class GuardSandboxReq(BaseModel):
    source: str | None = None
    ttl_seconds: int = Field(default=3600, ge=60, le=604800)


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

    def guard_root() -> Path:
        return Path(os.environ.get("TIER1_GUARD_ROOT", str(Path(__file__).resolve().parent.parent))).resolve()

    def sandbox_jobs():
        from .sandbox_lifecycle import SandboxJobManager, SandboxLifecycle
        parent = os.environ.get("TIER1_SANDBOX_PARENT", "").strip()
        if not parent:
            raise HTTPException(409, "sandbox lifecycle parent is not configured")
        parent_path = Path(parent).resolve()
        manager = getattr(app.state, "sandbox_jobs", None)
        if manager is None or manager.lifecycle.parent != parent_path:
            manager = SandboxJobManager(SandboxLifecycle(parent_path), svc.store)
            app.state.sandbox_jobs = manager
        return manager

    def sandbox_lifecycle():
        return sandbox_jobs().lifecycle

    def bound_sandbox_root(sandbox_id: str | None) -> tuple[str, Path]:
        """Resolve the persisted sandbox identity; writes never fall back to the live checkout."""
        if not sandbox_id:
            raise HTTPException(409, "approval is not bound to a sandbox")
        try:
            record = sandbox_lifecycle().inspect(sandbox_id)
        except (OSError, ValueError, RuntimeError) as exc:
            raise HTTPException(409, f"sandbox binding is invalid: {exc}")
        if record.expires_at <= time.time():
            raise HTTPException(409, "sandbox binding has expired")
        return sandbox_id, record.root

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
        durable = svc.store.backend == "postgres"
        return {"status": "ok", "provider": s.provider, "auth": "enabled" if s.api_token else "disabled",
                "skills": len(svc.skills.skills), "persistence": svc.store.backend,
                "durable": durable, "warning": None if durable else "SQLite storage is ephemeral"}

    @app.post("/v1/guard/agent/prepare", dependencies=[Depends(auth)])
    async def guard_agent_prepare(req: GuardAgentReq):
        """Run the real agent in proposal mode; it never writes files."""
        result = await svc.modes.run(req.prompt, mode="plan", tier=req.tier, trigger="guard:prepare")
        return {"status": result.get("status"), "run_id": result.get("run_id"),
                "answer": result.get("answer"), "audit": result.get("audit"),
                "usage": result.get("usage"), "evidence_level": "local",
                "write_execution": "not performed"}

    @app.get("/v1/guard/browser-repair", dependencies=[Depends(auth)])
    def guard_browser_repair(request: Request):
        """Run the integrated LAB guard in read-only mode; never claims browser proof."""
        lab_root = Path(__file__).resolve().parent.parent / "LAB"
        if str(lab_root.parent) not in sys.path:
            sys.path.insert(0, str(lab_root.parent))
        from LAB.tier1_guard_adapter import inspect_browser_repair
        result = inspect_browser_repair(lab_root.parent, request.url.port or 8000, "Tier-1 Control Plane")
        from LAB.repository_adapter import inspect_repository
        repository = inspect_repository(lab_root.parent)
        return {"status": result.status, "stopped_at": result.stopped_at, "reason": result.reason,
                "runtime_status": result.runtime_status, "scope_status": result.scope_status,
                "safety_status": result.safety_status, "impact_status": result.impact_status,
                "evidence_status": result.evidence_status, "evidence_level": "local-unavailable",
                "repository": repository.__dict__}

    @app.post("/v1/guard/browser-repair", dependencies=[Depends(auth)])
    def guard_browser_repair_request(req: GuardRepairReq, request: Request):
        """Accept a real repair request while keeping the integrated path read-only."""
        lab_root = Path(__file__).resolve().parent.parent / "LAB"
        if str(lab_root.parent) not in sys.path:
            sys.path.insert(0, str(lab_root.parent))
        from LAB.tier1_guard_adapter import inspect_browser_repair
        result = inspect_browser_repair(lab_root.parent, request.url.port or 8000,
                                        "Tier-1 Control Plane", goal=req.prompt)
        from LAB.repository_adapter import inspect_repository
        repository = inspect_repository(lab_root.parent)
        return {"request": req.prompt, "status": result.status, "stopped_at": result.stopped_at,
                "reason": result.reason, "runtime_status": result.runtime_status,
                "scope_status": result.scope_status, "safety_status": result.safety_status,
                "impact_status": result.impact_status, "evidence_status": result.evidence_status,
                "evidence_level": "local-unavailable", "repository": repository.__dict__}

    @app.get("/v1/guard/snapshot", dependencies=[Depends(auth)])
    def guard_snapshot(request: Request):
        """Read-only exact baseline snapshot for an approval proposal."""
        root = guard_root()
        sandbox_id = request.query_params.get("sandbox_id")
        if sandbox_id:
            _, root = bound_sandbox_root(sandbox_id)
        from LAB.repository_adapter import inspect_repository
        repository = inspect_repository(root)
        paths = [p for p in request.query_params.get("paths", "").split(",") if p]
        files = {}
        for path in sorted(set(paths)):
            target = (root / path).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                raise HTTPException(422, f"path escapes repository root: {path}")
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise HTTPException(409, f"unsafe snapshot path: {path}")
            files[path] = {"digest": "missing" if not target.exists() else hashlib.sha256(target.read_bytes()).hexdigest(),
                           "exists": target.exists()}
        return {"repository": repository.__dict__, "files": files, "evidence_level": "local"}

    @app.post("/v1/guard/sandboxes", status_code=202, dependencies=[Depends(auth)])
    def guard_sandbox_provision(req: GuardSandboxReq):
        try:
            job = sandbox_jobs().provision(req.source or str(guard_root()), req.ttl_seconds)
            return job
        except (OSError, ValueError, RuntimeError) as exc:
            raise HTTPException(409, str(exc))

    @app.post("/v1/guard/sandboxes/cleanup", status_code=202, dependencies=[Depends(auth)])
    def guard_sandbox_cleanup_expired():
        try:
            return sandbox_jobs().cleanup_expired()
        except (OSError, ValueError, RuntimeError) as exc:
            raise HTTPException(409, str(exc))

    @app.get("/v1/guard/sandboxes/jobs/{job_id}", dependencies=[Depends(auth)])
    def guard_sandbox_job(job_id: str):
        job = sandbox_jobs().get(job_id)
        if not job:
            raise HTTPException(404, "sandbox job not found")
        return job

    @app.delete("/v1/guard/sandboxes/jobs/{job_id}", status_code=202, dependencies=[Depends(auth)])
    def guard_sandbox_job_cancel(job_id: str):
        manager = sandbox_jobs()
        if not manager.cancel(job_id):
            raise HTTPException(409, "sandbox job is not cancellable")
        return manager.get(job_id)

    @app.delete("/v1/guard/sandboxes/{sandbox_id}", status_code=202, dependencies=[Depends(auth)])
    def guard_sandbox_cleanup(sandbox_id: str, force: bool = False):
        try:
            return sandbox_jobs().cleanup(sandbox_id, force=force)
        except (OSError, ValueError, RuntimeError) as exc:
            raise HTTPException(409, str(exc))

    def sandbox_view(record):
        from LAB.repository_adapter import inspect_repository
        try:
            repository = inspect_repository(record.root).__dict__
            status = "EXPIRED" if record.expires_at <= time.time() else "READY"
        except (OSError, ValueError, RuntimeError) as exc:
            repository = {"status": "UNAVAILABLE", "error": str(exc)}
            status = "UNAVAILABLE"
        return {"sandbox_id": record.sandbox_id, "root": str(record.root),
                "source": record.source, "expires_at": record.expires_at,
                "status": status, "repository": repository,
                "evidence_level": "local"}

    @app.get("/v1/guard/sandboxes", dependencies=[Depends(auth)])
    def guard_sandbox_list():
        try:
            manager = sandbox_lifecycle()
            return {"sandboxes": [sandbox_view(record) for record in manager.list()],
                    "evidence_level": "local"}
        except (OSError, ValueError, RuntimeError) as exc:
            raise HTTPException(409, str(exc))

    @app.get("/v1/guard/sandboxes/{sandbox_id}", dependencies=[Depends(auth)])
    def guard_sandbox_detail(sandbox_id: str):
        try:
            return sandbox_view(sandbox_lifecycle().inspect(sandbox_id))
        except (OSError, ValueError, RuntimeError) as exc:
            raise HTTPException(404, str(exc))

    @app.post("/v1/guard/write", dependencies=[Depends(auth)])
    def guard_write(req: GuardWriteReq):
        """Opt-in local write boundary bound to one persisted approval record."""
        if os.environ.get("TIER1_GUARD_WRITES") != "1":
            raise HTTPException(403, "guard writes are disabled; set TIER1_GUARD_WRITES=1 explicitly")
        if not req.approved:
            raise HTTPException(409, "explicit write approval is required")
        record = svc.store.approval_get(req.approval_id)
        if not record:
            raise HTTPException(404, "approval record not found")
        if record["status"] != "APPROVED":
            raise HTTPException(409, "approval record is not explicitly approved")
        stored = record["body"]
        if stored.get("explicit_approval") is not True:
            raise HTTPException(409, "approval record lacks explicit approval evidence")
        stored_files = {item["path"]: item.get("proposed") for item in stored.get("files", [])
                        if item.get("owner") == "ai"}
        stored_ai = set(stored.get("ownership", {}).get("ai_files", []))
        stored_user = set(stored.get("ownership", {}).get("protected_user_files", []))
        stored_digests = {item["path"]: item.get("baseline_digest", "") for item in stored.get("files", [])}
        if (req.branch != stored.get("repository", {}).get("branch") or
                req.commit != stored.get("repository", {}).get("commit") or
                req.files != stored_files or set(req.ai_files) != stored_ai or
                set(req.protected_user_files) != stored_user or req.baseline_digests != stored_digests):
            raise HTTPException(409, "write request does not exactly match persisted approval")
        if stored.get("evidence_level") not in ("local", "browser", "journey"):
            raise HTTPException(409, "approval evidence is not current enough for a write")
        if req.agent_run_id != (stored.get("agent") or {}).get("run_id"):
            raise HTTPException(409, "write request does not match the persisted agent run")
        if req.agent_run_id:
            agent_run = svc.store.run_get(req.agent_run_id)
            if not agent_run or agent_run.get("status") != "ok":
                raise HTTPException(409, "agent run is not successful")
        stored_sandbox = stored.get("sandbox", {})
        if req.sandbox_id != stored_sandbox.get("sandbox_id"):
            raise HTTPException(409, "write request does not match the persisted sandbox")
        _, root = bound_sandbox_root(stored_sandbox.get("sandbox_id"))
        from LAB.repository_adapter import inspect_repository
        from LAB.rollback_guard import FileOwnership, OwnershipConfirmation, plan_rollback
        from LAB.sandboxed_write_executor import execute_sandboxed_write
        repository = inspect_repository(root)
        if not repository.is_git:
            raise HTTPException(409, "repository is not a Git worktree")
        if (repository.branch != req.branch or repository.commit != req.commit or
                repository.dirty != stored.get("repository", {}).get("dirty")):
            raise HTTPException(409, "repository identity changed since approval")
        all_paths = set(req.ai_files) | set(req.protected_user_files)
        if set(req.files) != set(req.ai_files):
            raise HTTPException(422, "files must exactly match ai_files")
        if set(req.baseline_digests) != all_paths:
            raise HTTPException(422, "baseline_digests must cover AI and protected user files")
        ownership = tuple(
            FileOwnership(path, req.baseline_digests[path], "", "ai" if path in req.ai_files else "user")
            for path in sorted(all_paths)
        )
        rollback = plan_rollback(ownership)
        result = execute_sandboxed_write(
            root, req.files, rollback=rollback,
            ownership=OwnershipConfirmation(req.commit, req.branch, tuple(req.ai_files), tuple(req.protected_user_files)),
            repository_commit=repository.commit, repository_branch=repository.branch,
        )
        audit_id = uuid.uuid4().hex
        audit_body = {"approval_id": req.approval_id, "agent_run_id": req.agent_run_id,
                      "result": result.__dict__,
                      "repository": repository.__dict__, "evidence_level": "local",
                      "post_write_evidence": result.status == "WRITTEN"}
        svc.store.write_audit_put(audit_id, req.approval_id, "write", result.status, audit_body)
        updated = dict(stored)
        updated["write_execution"] = result.status.lower()
        updated["write_audit_id"] = audit_id
        updated["post_write_evidence"] = audit_body["post_write_evidence"]
        svc.store.approval_put(req.approval_id, "APPROVED", updated)
        return {"status": result.status, "written_files": result.written_files,
                "changed_files": result.changed_files, "reason": result.reason,
                "repository": repository.__dict__, "evidence_level": "local",
                "audit_id": audit_id, "post_write_evidence": audit_body["post_write_evidence"]}

    @app.get("/v1/guard/approvals/{approval_id}/audits", dependencies=[Depends(auth)])
    def guard_write_audits(approval_id: str):
        if not svc.store.approval_get(approval_id):
            raise HTTPException(404, "approval record not found")
        return svc.store.write_audits_list(approval_id)

    @app.post("/v1/guard/approvals/{approval_id}/rollback", dependencies=[Depends(auth)])
    def guard_approval_rollback(approval_id: str, req: GuardRollbackReq):
        if not req.approved:
            raise HTTPException(409, "explicit rollback approval is required")
        record = svc.store.approval_get(approval_id)
        if not record:
            raise HTTPException(404, "approval record not found")
        body = record["body"]
        audit_id = body.get("write_audit_id")
        audit = svc.store.write_audit_get(audit_id) if audit_id else None
        if not audit or audit["action"] != "write" or audit["status"] != "WRITTEN":
            raise HTTPException(409, "no successful audited write is available for rollback")
        _, root = bound_sandbox_root((body.get("sandbox") or {}).get("sandbox_id"))
        from LAB.repository_adapter import inspect_repository
        from LAB.rollback_guard import FileOwnership, OwnershipConfirmation, plan_rollback
        from LAB.sandboxed_write_executor import execute_sandboxed_rollback
        repository = inspect_repository(root)
        stored_repo = body.get("repository", {})
        if (repository.branch != stored_repo.get("branch") or repository.commit != stored_repo.get("commit")):
            raise HTTPException(409, "repository identity changed since approval")
        files = {item["path"]: item for item in body.get("files", [])}
        ai_files = list(body.get("ownership", {}).get("ai_files", []))
        user_files = list(body.get("ownership", {}).get("protected_user_files", []))
        baseline = {path: files[path].get("current") for path in ai_files}
        expected = {path: hashlib.sha256((files[path].get("proposed") or "").encode("utf-8")).hexdigest()
                    for path in ai_files}
        protected = {path: files[path].get("baseline_digest", "") for path in user_files}
        ownership = tuple(FileOwnership(path, files[path].get("baseline_digest", "missing"), expected[path], "ai") for path in ai_files) + tuple(
            FileOwnership(path, files[path].get("baseline_digest", "missing"), files[path].get("baseline_digest", "missing"), "user") for path in user_files)
        rollback = plan_rollback(ownership)
        result = execute_sandboxed_rollback(root, baseline, expected_current_digests=expected,
            protected_user_digests=protected, rollback=rollback,
            ownership=OwnershipConfirmation(repository.commit, repository.branch, tuple(ai_files), tuple(user_files)),
            repository_commit=repository.commit, repository_branch=repository.branch)
        rollback_audit = uuid.uuid4().hex
        audit_body = {"approval_id": approval_id, "result": result.__dict__, "repository": repository.__dict__,
                      "evidence_level": "local", "rollback_evidence": result.status == "ROLLED_BACK"}
        svc.store.write_audit_put(rollback_audit, approval_id, "rollback", result.status, audit_body)
        updated = dict(body)
        updated["rollback_execution"] = result.status.lower()
        updated["rollback_audit_id"] = rollback_audit
        svc.store.approval_put(approval_id, "APPROVED", updated)
        return {"status": result.status, "restored_files": result.restored_files,
                "protected_files": result.protected_files, "reason": result.reason,
                "audit_id": rollback_audit, "rollback_evidence": audit_body["rollback_evidence"]}

    @app.post("/v1/guard/approvals/{approval_id}/approve", dependencies=[Depends(auth)])
    def guard_approval_approve(approval_id: str):
        """Explicitly approve only a clean, current, reversible proposal."""
        record = svc.store.approval_get(approval_id)
        if not record:
            raise HTTPException(404, "approval record not found")
        if record["status"] != "REVIEW":
            raise HTTPException(409, "only REVIEW approval records can be approved")
        body = record["body"]
        if body.get("write_execution") != "not performed" or body.get("rollback", {}).get("status") != "READY":
            raise HTTPException(409, "approval evidence or rollback plan is not ready")
        sandbox_id = (body.get("sandbox") or {}).get("sandbox_id")
        root = bound_sandbox_root(sandbox_id)[1] if sandbox_id else guard_root()
        repository = body.get("repository", {})
        from LAB.repository_adapter import inspect_repository
        current = inspect_repository(root)
        if (current.branch != repository.get("branch") or current.commit != repository.get("commit") or
                current.dirty != repository.get("dirty")):
            raise HTTPException(409, "repository identity changed since approval preview")
        for item in body.get("files", []):
            if item.get("owner") != "ai":
                continue
            target = (root / item["path"]).resolve()
            if not target.is_file():
                if item.get("baseline_digest") != "missing":
                    raise HTTPException(409, f"baseline drift detected: {item['path']}")
            else:
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                if digest != item.get("baseline_digest"):
                    raise HTTPException(409, f"baseline drift detected: {item['path']}")
        body = dict(body)
        body["explicit_approval"] = True
        body["approved_at"] = time.time()
        svc.store.approval_put(approval_id, "APPROVED", body)
        return {"approval_id": approval_id, "status": "APPROVED", "write_execution": "not performed"}

    @app.post("/v1/guard/approval", dependencies=[Depends(auth)])
    def guard_approval(req: GuardApprovalReq):
        """Build a read-only approval brief; this route never writes files."""
        root = guard_root() if not req.sandbox_id else bound_sandbox_root(req.sandbox_id)[1]
        from LAB.repository_adapter import inspect_repository
        from LAB.rollback_guard import FileOwnership, OwnershipConfirmation, plan_rollback, ownership_mismatch
        repository = inspect_repository(root)
        all_paths = set(req.ai_files) | set(req.protected_user_files)
        issues: list[str] = []
        if set(req.files) != set(req.ai_files):
            issues.append("proposed files must exactly match AI-owned files")
        if set(req.baseline_digests) != all_paths:
            issues.append("baseline digests must cover AI and protected user files")
        ownership = tuple(FileOwnership(path, req.baseline_digests.get(path, ""), "",
                                        "ai" if path in req.ai_files else "user")
                          for path in sorted(all_paths))
        plan = plan_rollback(ownership)
        confirmation = OwnershipConfirmation(req.commit, req.branch, tuple(req.ai_files),
                                             tuple(req.protected_user_files))
        mismatch = ownership_mismatch(plan, confirmation,
                                      repository_commit=repository.commit,
                                      repository_branch=repository.branch)
        if mismatch:
            issues.append(mismatch)
        if repository.dirty:
            issues.append("worktree is dirty; pre-existing changes require explicit review")
        files = []
        for path in sorted(req.ai_files):
            target = (root / path).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                issues.append(f"path escapes repository root: {path}")
                current = None
            else:
                current = target.read_text(encoding="utf-8") if target.is_file() else None
            files.append({"path": path, "owner": "ai", "current": current,
                          "proposed": req.files.get(path),
                          "baseline_digest": req.baseline_digests.get(path, "")})
        files.extend({"path": path, "owner": "user", "current": None,
                      "proposed": None, "baseline_digest": req.baseline_digests.get(path, "")}
                     for path in sorted(req.protected_user_files))
        status = "BLOCKED" if issues or plan.status != "READY" else "REVIEW"
        agent = None
        if req.agent_run_id:
            agent_run = svc.store.run_get(req.agent_run_id)
            if not agent_run or agent_run.get("status") != "ok":
                issues.append("agent run must exist and be successful")
            else:
                agent = {"run_id": req.agent_run_id, "status": agent_run["status"]}
        response = {"status": status, "approval_required": True, "writes_enabled": os.environ.get("TIER1_GUARD_WRITES") == "1",
                "goal": req.goal, "repository": repository.__dict__, "files": files,
                "ownership": {"ai_files": list(plan.ai_files), "protected_user_files": list(plan.protected_user_files)},
                "risks": issues or ["no blocking findings; human approval still required"],
                "rollback": {"status": plan.status, "instructions": list(plan.instructions),
                             "irreversible": list(plan.irreversible)},
                "evidence_level": "local", "write_execution": "not performed",
                "agent": agent}
        if req.sandbox_id:
            _, sandbox_root = bound_sandbox_root(req.sandbox_id)
            sandbox_repository = inspect_repository(sandbox_root)
            response["sandbox"] = {"sandbox_id": req.sandbox_id, "root": str(sandbox_root),
                                   "expires_at": sandbox_lifecycle().inspect(req.sandbox_id).expires_at,
                                   "repository": sandbox_repository.__dict__}
        else:
            response["sandbox"] = {"sandbox_id": None, "status": "UNBOUND",
                                    "reason": "writes and rollback require a provisioned sandbox"}
        record_id = uuid.uuid4().hex
        svc.store.approval_put(record_id, status, response)
        response["approval_id"] = record_id
        return response

    @app.get("/v1/guard/approvals", dependencies=[Depends(auth)])
    def guard_approvals(limit: int = 50):
        return svc.store.approvals_list(min(limit, 200))

    @app.get("/v1/guard/approvals/{approval_id}", dependencies=[Depends(auth)])
    def guard_approval_get(approval_id: str):
        record = svc.store.approval_get(approval_id)
        if not record:
            raise HTTPException(404, "approval record not found")
        return record

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
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
