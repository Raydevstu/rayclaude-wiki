"""Outbound notifications (Slack-compatible JSON, HMAC-signed). Never raises into the caller."""
from __future__ import annotations
import hashlib, hmac, json, logging, time

import httpx

from .safety import check_url, redact

log = logging.getLogger("tier1")


class Notifier:
    def __init__(self, settings, transport=None):
        self.s, self.transport = settings, transport

    async def send(self, event: str, text: str, data: dict | None = None) -> bool:
        url = self.s.notify_url
        if not url:
            return False
        ok, why = check_url(url, self.s.http_allowlist)
        if not ok:
            log.warning("notify blocked: %s", why)
            return False
        body = json.dumps({"event": event, "text": redact(text)[0][:2800], "data": data or {}}, default=str).encode()
        ts = str(int(time.time()))
        headers = {"Content-Type": "application/json", "X-Tier1-Timestamp": ts}
        if self.s.webhook_secret:
            headers["X-Tier1-Signature"] = hmac.new(self.s.webhook_secret.encode(), f"{ts}.".encode() + body,
                                                    hashlib.sha256).hexdigest()
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False, transport=self.transport) as c:
                r = await c.post(url, content=body, headers=headers)
            return r.status_code < 300
        except httpx.HTTPError as e:
            log.warning("notify failed: %s", type(e).__name__)
            return False
