from __future__ import annotations
import ast, operator as op, re
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx

from .config import Settings
from .safety import check_url, safe_path

_OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.Mod: op.mod,
        ast.FloorDiv: op.floordiv, ast.Pow: op.pow}
MAX_BYTES = 500_000


class ToolError(Exception):
    pass


def calc(expr: str):
    if len(expr) > 200:
        raise ToolError("expression too long")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and (abs(b) > 100 or abs(a) > 1e6):
                raise ToolError("exponent too large")
            return _OPS[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            v = ev(n.operand)
            return v if isinstance(n.op, ast.UAdd) else -v
        raise ToolError("unsupported expression")

    try:
        return ev(ast.parse(expr.replace("^", "**").strip(), mode="eval"))
    except (SyntaxError, ZeroDivisionError, OverflowError) as e:
        raise ToolError(str(e) or "invalid expression")


class Tools:
    NAMES = ("calc", "now", "read_file", "list_files", "http_get", "kb_search")

    def __init__(self, s: Settings, transport=None, kb=None):
        self.s, self.transport, self.kb = s, transport, kb

    async def call(self, name: str, args: dict) -> str:
        if name not in self.NAMES:
            raise ToolError(f"unknown tool: {name}")
        if name == "kb_search":
            if self.kb is None:
                raise ToolError("knowledge base unavailable")
            try:
                hits = self.kb.search(str(args.get("notebook", "session")), str(args.get("query", "")), 5)
            except ValueError as e:
                raise ToolError(str(e))
            return "\n\n".join(f"[{h['n']}] {h['source']}#{h['chunk']}: {h['text']}" for h in hits) or "(no matches)"
        if name == "calc":
            return str(calc(str(args.get("expr", ""))))
        if name == "now":
            return datetime.now(timezone.utc).isoformat()
        if name == "read_file":
            try:
                p = safe_path(self.s.sandbox_dir, str(args.get("path", "")))
            except PermissionError as e:
                raise ToolError(str(e))
            if not p.is_file():
                raise ToolError("file not found")
            if p.stat().st_size > 200_000:
                raise ToolError("file too large")
            return p.read_text(errors="replace")
        if name == "list_files":
            try:
                p = safe_path(self.s.sandbox_dir, str(args.get("path", ".")))
            except PermissionError as e:
                raise ToolError(str(e))
            return "\n".join(sorted(x.name for x in p.iterdir())[:200]) if p.is_dir() else ""
        return await self._http_get(str(args.get("url", "")))

    async def fetch_raw(self, url: str, max_bytes: int = 5_000_000) -> tuple[bytes, str]:
        """Fetch bytes with the same SSRF checks, manual redirect validation and size cap as http_get."""
        for _ in range(4):
            ok, why = check_url(url, self.s.http_allowlist)
            if not ok:
                raise ToolError(why)
            try:
                async with httpx.AsyncClient(timeout=15, follow_redirects=False, transport=self.transport) as c:
                    r = await c.get(url, headers={"User-Agent": "tier1-agent/1.0"})
            except httpx.HTTPError as e:
                raise ToolError(f"fetch failed: {type(e).__name__}")
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                continue
            if r.status_code >= 400:
                raise ToolError(f"HTTP {r.status_code}")
            if len(r.content) > max_bytes:
                raise ToolError("document too large")
            return r.content, r.headers.get("content-type", "")
        raise ToolError("too many redirects")

    async def _http_get(self, url: str) -> str:
        for _ in range(4):
            ok, why = check_url(url, self.s.http_allowlist)
            if not ok:
                raise ToolError(why)
            try:
                async with httpx.AsyncClient(timeout=10, follow_redirects=False, transport=self.transport) as c:
                    r = await c.get(url, headers={"User-Agent": "tier1-agent/1.0"})
            except httpx.HTTPError as e:
                raise ToolError(f"fetch failed: {type(e).__name__}")
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                continue
            if r.status_code >= 400:
                raise ToolError(f"HTTP {r.status_code}")
            ctype = r.headers.get("content-type", "")
            if not any(t in ctype for t in ("text/", "json", "xml")):
                raise ToolError("unsupported content type")
            text = r.text[:MAX_BYTES]
            if "html" in ctype:
                text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
                text = re.sub(r"(?s)<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
            return text
        raise ToolError("too many redirects")
