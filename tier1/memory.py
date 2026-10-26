from __future__ import annotations

from datetime import datetime, timezone

from .memory_remote import RemoteMemory, RemoteMemoryError


class MemoryAdapter:
    """One project-scoped memory contract for API and MCP callers."""

    def __init__(self, settings, store):
        self.settings = settings
        self.store = store

    @property
    def project_id(self) -> str:
        return self.settings.memory_project_id

    def _envelope(self, *, status: str, source: str, results=None, error=None) -> dict:
        body = {
            "ok": status == "available",
            "status": status,
            "source": source,
            "project_id": self.project_id,
            "provenance": "tier1-memory",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if results is not None:
            body["results"] = results
        if error:
            body["error"] = error
        return body

    def add(self, text: str, tags: str = "") -> dict:
        if self.settings.memory_url:
            try:
                result = RemoteMemory(self.settings).capture({"text": text, "tags": tags})
                return {**self._envelope(status="available", source="remote"), "remote": result}
            except RemoteMemoryError as exc:
                return self._envelope(status="failed", source="remote", error=str(exc))
        self.store.memory_add(text, tags)
        return self._envelope(status="available", source=self.store.backend)

    def search(self, query: str, k: int = 3) -> dict:
        if self.settings.memory_url:
            try:
                result = RemoteMemory(self.settings).search(query)
                return {**self._envelope(status="available", source="remote"), "remote": result}
            except RemoteMemoryError as exc:
                return self._envelope(status="failed", source="remote", error=str(exc))
        return self._envelope(status="available", source=self.store.backend,
                              results=self.store.memory_search(query, k))

    def remote_status(self) -> dict:
        if self.settings.memory_url and all((self.settings.memory_tenant_id,
                                             self.settings.memory_bank_id,
                                             self.settings.memory_project_id)):
            return self._envelope(status="configured", source="remote")
        return self._envelope(status="unavailable", source="local",
                              error="TIER1_MEMORY_URL and scoped tenant/bank/project are required for remote memory")
