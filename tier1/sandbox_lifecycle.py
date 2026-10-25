"""Provision and retire isolated Tier-1 workspaces without touching production paths."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

from .sandbox_adapter import MARKER


MANIFEST = ".tier1-sandbox.json"
VERSION = "tier1-sandbox-v1"


class SandboxCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class SandboxRecord:
    sandbox_id: str
    root: Path
    expires_at: float
    source: str


class SandboxLifecycle:
    def __init__(self, parent: str | Path):
        self.parent = Path(parent).resolve()
        self.parent.mkdir(parents=True, exist_ok=True)
        if self.parent.parent == self.parent:
            raise ValueError("sandbox parent cannot be filesystem root")

    def provision(self, source: str | Path, ttl_seconds: int = 3600, *,
                  cancel_event: threading.Event | None = None, progress=None) -> SandboxRecord:
        source_path = Path(source).resolve()
        if not source_path.is_dir() or source_path == self.parent:
            raise ValueError("source must be a directory outside the sandbox parent")
        if source_path.is_relative_to(self.parent):
            raise ValueError("source cannot be inside the sandbox parent")
        if ttl_seconds < 60 or ttl_seconds > 7 * 24 * 3600:
            raise ValueError("sandbox TTL must be between 60 seconds and 7 days")
        sandbox_id = uuid.uuid4().hex
        root = self.parent / sandbox_id
        try:
            self._progress(progress, 5, "copying")
            self._check_cancel(cancel_event)
            shutil.copytree(source_path, root, ignore=shutil.ignore_patterns(".git", "__pycache__", ".tier1-sandbox*"))
            self._progress(progress, 55, "initializing")
            self._check_cancel(cancel_event)
            (root / MARKER).write_text(VERSION + "\n", encoding="utf-8")
            expires_at = time.time() + ttl_seconds
            (root / MANIFEST).write_text(json.dumps({"version": VERSION, "sandbox_id": sandbox_id,
                "expires_at": expires_at, "source": str(source_path)}, sort_keys=True) + "\n", encoding="utf-8")
            self._git(root, "init", "-b", "main")
            self._git(root, "config", "user.email", "tier1-sandbox@invalid")
            self._git(root, "config", "user.name", "Tier-1 Sandbox")
            self._git(root, "add", ".")
            self._progress(progress, 85, "committing baseline")
            self._check_cancel(cancel_event)
            self._git(root, "commit", "-m", "sandbox baseline")
            self._check_cancel(cancel_event)
            self._progress(progress, 100, "ready")
            return SandboxRecord(sandbox_id, root, expires_at, str(source_path))
        except Exception:
            if root.exists():
                self._remove_tree(root)
            raise

    def inspect(self, sandbox_id: str) -> SandboxRecord:
        root = self._root(sandbox_id)
        try:
            data = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("sandbox manifest is invalid") from exc
        if data.get("version") != VERSION or data.get("sandbox_id") != sandbox_id:
            raise ValueError("sandbox identity is invalid")
        return SandboxRecord(sandbox_id, root, float(data["expires_at"]), str(data.get("source", "")))

    def list(self) -> list[SandboxRecord]:
        records = []
        for child in sorted(self.parent.iterdir(), key=lambda item: item.name):
            if not child.is_dir() or child.is_symlink() or not (child / MANIFEST).is_file():
                continue
            try:
                records.append(self.inspect(child.name))
            except (OSError, ValueError):
                continue
        return records

    def cleanup(self, sandbox_id: str, *, force: bool = False) -> bool:
        record = self.inspect(sandbox_id)
        if not force and record.expires_at > time.time():
            raise ValueError("sandbox has not expired")
        if record.root == self.parent or not record.root.is_relative_to(self.parent):
            raise ValueError("refusing cleanup outside sandbox parent")
        # Git may mark object files read-only on Windows; make only this owned tree removable.
        for path in record.root.rglob("*"):
            try:
                path.chmod(path.stat().st_mode | 0o200)
            except OSError:
                pass
        shutil.rmtree(record.root)
        return True

    def cleanup_expired(self) -> list[str]:
        removed = []
        for child in self.parent.iterdir():
            if not child.is_dir() or child.is_symlink() or not (child / MANIFEST).is_file():
                continue
            try:
                record = self.inspect(child.name)
                if record.expires_at <= time.time():
                    self.cleanup(record.sandbox_id)
                    removed.append(record.sandbox_id)
            except (OSError, ValueError):
                continue
        return removed

    @staticmethod
    def _check_cancel(cancel_event: threading.Event | None) -> None:
        if cancel_event and cancel_event.is_set():
            raise SandboxCancelled("sandbox provisioning cancelled")

    @staticmethod
    def _progress(progress, value: int, message: str) -> None:
        if progress:
            progress(value, message)

    @staticmethod
    def _remove_tree(root: Path) -> None:
        for path in root.rglob("*"):
            try:
                path.chmod(path.stat().st_mode | 0o200)
            except OSError:
                pass
        shutil.rmtree(root, ignore_errors=True)

    def _root(self, sandbox_id: str) -> Path:
        if not sandbox_id or Path(sandbox_id).name != sandbox_id:
            raise ValueError("invalid sandbox id")
        root = (self.parent / sandbox_id).resolve()
        if not root.is_relative_to(self.parent) or not root.is_dir():
            raise ValueError("sandbox not found")
        return root

    @staticmethod
    def _git(root: Path, *args: str) -> None:
        # Sandbox baselines must not execute hooks inherited from the user's checkout.
        subprocess.run(["git", "-c", f"core.hooksPath={os.devnull}", "-C", str(root), *args], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


class SandboxJobManager:
    """Process-local async job state; only completed jobs publish a sandbox."""

    def __init__(self, lifecycle: SandboxLifecycle, store=None, max_retained_jobs: int = 500):
        self.lifecycle = lifecycle
        self.store = store
        self.max_retained_jobs = max(1, int(max_retained_jobs))
        self._jobs: dict[str, dict] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._cleanup_claims: set[str] = set()
        self._cleanup_scan_lock = threading.Lock()
        self._lock = threading.RLock()
        if store:
            for job in store.sandbox_jobs_list():
                if job["status"] in {"QUEUED", "PROVISIONING", "CANCELLING", "CLEANING"}:
                    job.update(status="FAILED", message="interrupted by process restart",
                               reason="interrupted by process restart")
                self._jobs[job["job_id"]] = job
                self._cancel[job["job_id"]] = threading.Event()
                self._save(job["job_id"])
            store.sandbox_jobs_prune(self.max_retained_jobs)

    def provision(self, source: str | Path, ttl_seconds: int) -> dict:
        return self._start("provision", self._run_provision, str(source), ttl_seconds)

    def cleanup(self, sandbox_id: str, force: bool) -> dict:
        return self._start("cleanup", self._run_cleanup, sandbox_id, force)

    def cleanup_expired(self) -> dict:
        return self._start("cleanup_expired", self._run_cleanup_expired)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job["status"] not in {"QUEUED", "PROVISIONING"}:
                return False
            self._cancel[job_id].set()
            job["status"] = "CANCELLING"
            job["message"] = "cancellation requested"
            self._save(job_id)
            return True

    def _start(self, kind: str, target, *args) -> dict:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = {"job_id": job_id, "kind": kind, "status": "QUEUED",
                                  "progress": 0, "message": "queued", "evidence_level": "local"}
            self._cancel[job_id] = threading.Event()
            self._save(job_id)
        threading.Thread(target=target, args=(job_id, *args), daemon=True).start()
        return self.get(job_id)

    def _update(self, job_id: str, **changes) -> None:
        with self._lock:
            self._jobs[job_id].update(changes)
            self._save(job_id)

    def _save(self, job_id: str) -> None:
        if self.store:
            job = self._jobs[job_id]
            self.store.sandbox_job_put(job_id, job["status"], job)
            self.store.sandbox_jobs_prune(self.max_retained_jobs)

    def _run_provision(self, job_id: str, source: str, ttl_seconds: int) -> None:
        cancel = self._cancel[job_id]
        self._update(job_id, status="PROVISIONING", message="starting")
        try:
            record = self.lifecycle.provision(
                source, ttl_seconds, cancel_event=cancel,
                progress=lambda value, message: self._update(job_id, progress=value, message=message),
            )
        except Exception as exc:
            status = "CANCELLED" if cancel.is_set() else "FAILED"
            self._update(job_id, status=status, message=str(exc), reason=str(exc))
        else:
            self._update(job_id, status="READY", progress=100, message="ready",
                         sandbox_id=record.sandbox_id, root=str(record.root),
                         expires_at=record.expires_at, source=record.source)

    def _run_cleanup(self, job_id: str, sandbox_id: str, force: bool) -> None:
        with self._lock:
            if sandbox_id in self._cleanup_claims:
                self._update(job_id, status="FAILED", message="cleanup already in progress",
                             reason="cleanup already in progress")
                return
            self._cleanup_claims.add(sandbox_id)
        self._update(job_id, status="CLEANING", progress=10, message="removing sandbox")
        try:
            self.lifecycle.cleanup(sandbox_id, force=force)
        except Exception as exc:
            self._update(job_id, status="FAILED", message=str(exc), reason=str(exc))
        else:
            self._update(job_id, status="REMOVED", progress=100, message="removed", sandbox_id=sandbox_id)
        finally:
            with self._lock:
                self._cleanup_claims.discard(sandbox_id)

    def _run_cleanup_expired(self, job_id: str) -> None:
        with self._cleanup_scan_lock:
            self._run_cleanup_expired_locked(job_id)

    def _run_cleanup_expired_locked(self, job_id: str) -> None:
        self._update(job_id, status="CLEANING", progress=10, message="scanning expired sandboxes")
        try:
            removed = self.lifecycle.cleanup_expired()
        except Exception as exc:
            self._update(job_id, status="FAILED", message=str(exc), reason=str(exc))
        else:
            self._update(job_id, status="CLEANED", progress=100, message="expired sandboxes removed",
                         removed_sandboxes=removed)
