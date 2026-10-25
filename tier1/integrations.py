"""Slack integration (slash command + app mentions). Requests are verified with Slack's v0 signing scheme."""
from __future__ import annotations
import asyncio, hashlib, hmac, logging, re, time
from urllib.parse import parse_qs, urlparse

import httpx

from .safety import redact

log = logging.getLogger("tier1")
MENTION_RE = re.compile(r"<@[A-Z0-9]+>")


def verify_slack(secret: str, ts: str, body: bytes, sig: str, now: float | None = None) -> bool:
    if not secret:
        return False
    try:
        if abs((now or time.time()) - float(ts)) > 300:
            return False
    except ValueError:
        return False
    want = "v0=" + hmac.new(secret.encode(), b"v0:" + ts.encode() + b":" + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(want, sig or "")


def valid_response_url(u: str) -> bool:
    p = urlparse(u)
    return p.scheme == "https" and (p.hostname or "").endswith(".slack.com") and p.port in (None, 443)


class Slack:
    def __init__(self, svc, transport=None):
        self.svc, self.transport, self.tasks = svc, transport, set()

    def spawn(self, coro):
        t = asyncio.create_task(coro)
        self.tasks.add(t)
        t.add_done_callback(self.tasks.discard)
        return t

    async def drain(self):
        while self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)

    async def _answer(self, text: str, who: str, session: str = "") -> str:
        try:
            if session:
                res = await self.svc.chat.send(session, text, trigger="slack")
            else:
                res = await self.svc.modes.run(text, trigger=f"slack:{who[:40]}")
        except Exception as e:                                     # never leak internals into a channel
            log.warning("slack run failed: %s", e)
            return f"Run failed ({type(e).__name__})."
        a = redact(res.get("answer", ""))[0][:2800]
        return f"{a}\n_run {res['run_id']} · {res['status']} · ${res['usage']['cost_usd']:.4f}_"

    async def command(self, form: dict):
        text = (form.get("text", [""])[0]).strip()
        url, who = form.get("response_url", [""])[0], form.get("user_name", ["?"])[0]
        if not text:
            return {"response_type": "ephemeral", "text": "Usage: /tier1 [ralph:|team:|plan:] <request>"}
        if not valid_response_url(url):
            return {"response_type": "ephemeral", "text": "Missing or untrusted response_url."}

        async def work():
            msg = await self._answer(text, who)
            async with httpx.AsyncClient(timeout=10, follow_redirects=False, transport=self.transport) as c:
                await c.post(url, json={"response_type": "in_channel", "text": msg})
        self.spawn(work())
        return {"response_type": "ephemeral", "text": "Working on it…"}

    async def event(self, payload: dict, retry: str = ""):
        if payload.get("type") == "url_verification":
            return {"challenge": str(payload.get("challenge", ""))}
        ev = payload.get("event") or {}
        if retry or payload.get("type") != "event_callback" or ev.get("type") != "app_mention" or ev.get("bot_id"):
            return {"ok": True}                                    # ignore retries and bot messages (no reply loops)
        token = self.svc.settings.slack_bot_token
        text = MENTION_RE.sub("", ev.get("text", "")).strip()
        if not token or not text or not ev.get("channel"):
            return {"ok": True}

        async def work():
            thread = ev.get("thread_ts") or ev.get("ts")
            msg = await self._answer(text, str(ev.get("user", "?")), f"slack-{ev['channel']}-{thread}")
            async with httpx.AsyncClient(timeout=10, follow_redirects=False, transport=self.transport) as c:
                await c.post("https://slack.com/api/chat.postMessage", headers={"Authorization": f"Bearer {token}"},
                             json={"channel": ev["channel"], "text": msg, "thread_ts": ev.get("thread_ts") or ev.get("ts")})
        self.spawn(work())
        return {"ok": True}
