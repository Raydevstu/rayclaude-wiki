from __future__ import annotations

import httpx


class RemoteMemoryError(RuntimeError):
    pass


class RemoteMemory:
    def __init__(self, settings):
        self.s = settings

    def _scope(self):
        values = (self.s.memory_tenant_id, self.s.memory_bank_id, self.s.memory_project_id)
        if not self.s.memory_url or not all(values):
            raise RemoteMemoryError("remote memory URL and tenant/bank/project scope are required")
        return dict(zip(("tenantId", "bankId", "projectId"), values))

    def _headers(self):
        if self.s.memory_authorization:
            return {"content-type": "application/json", "authorization": self.s.memory_authorization}
        return {"content-type": "application/json", "x-dev-subject": "tier1-memory", "x-dev-tenant-id": self.s.memory_tenant_id, "x-dev-scopes": "events:write memory:read memory:write"}

    def capture(self, payload: dict) -> dict:
        body = {**self._scope(), **payload}
        try:
            r = httpx.post(self.s.memory_url + "/api/project-memory/codex-event", json=body, headers=self._headers(), timeout=10)
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise RemoteMemoryError(f"remote memory capture failed: {e}") from e
        if r.status_code >= 400 or not data.get("ok"):
            raise RemoteMemoryError(data.get("error", f"remote memory HTTP {r.status_code}"))
        return data

    def search(self, query: str) -> dict:
        body = {**self._scope(), "query": query, "projection": "summary"}
        try:
            r = httpx.post(self.s.memory_url + "/api/v1/memory/recall", json=body, headers=self._headers(), timeout=15)
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise RemoteMemoryError(f"remote memory recall failed: {e}") from e
        if r.status_code >= 400 or not data.get("ok"):
            raise RemoteMemoryError(data.get("error", f"remote memory HTTP {r.status_code}"))
        return data
