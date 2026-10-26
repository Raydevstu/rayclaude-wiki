"""Provision and retire isolated Tier-1 workspaces without touching production paths."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

from .sandbox_adapter import MARKER


MANIFEST = ".tier1-sandbox.json"
VERSION = "tier1-sandbox-v1"


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

    def provision(self, source: str | Path, ttl_seconds: int = 3600) -> SandboxRecord:
        source_path = Path(source).resolve()
        if not source_path.is_dir() or source_path == self.parent:
            raise ValueError("source must be a directory outside the sandbox parent")
        if source_path.is_relative_to(self.parent):
            raise ValueError("source cannot be inside the sandbox parent")
        if ttl_seconds < 60 or ttl_seconds > 7 * 24 * 3600:
            raise ValueError("sandbox TTL must be between 60 seconds and 7 days")
        sandbox_id = uuid.uuid4().hex
        root = self.parent / sandbox_id
        shutil.copytree(source_path, root, ignore=shutil.ignore_patterns(".git", "__pycache__", ".tier1-sandbox*"))
        (root / MARKER).write_text(VERSION + "\n", encoding="utf-8")
        expires_at = time.time() + ttl_seconds
        (root / MANIFEST).write_text(json.dumps({"version": VERSION, "sandbox_id": sandbox_id,
            "expires_at": expires_at, "source": str(source_path)}, sort_keys=True) + "\n", encoding="utf-8")
        self._git(root, "init", "-b", "main")
        self._git(root, "config", "user.email", "tier1-sandbox@invalid")
        self._git(root, "config", "user.name", "Tier-1 Sandbox")
        self._git(root, "add", ".")
        self._git(root, "commit", "-m", "sandbox baseline")
        return SandboxRecord(sandbox_id, root, expires_at, str(source_path))

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

    def _root(self, sandbox_id: str) -> Path:
        if not sandbox_id or Path(sandbox_id).name != sandbox_id:
            raise ValueError("invalid sandbox id")
        root = (self.parent / sandbox_id).resolve()
        if not root.is_relative_to(self.parent) or not root.is_dir():
            raise ValueError("sandbox not found")
        return root

    @staticmethod
    def _git(root: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
