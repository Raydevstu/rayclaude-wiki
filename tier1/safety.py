from __future__ import annotations
import ipaddress, re, socket
from pathlib import Path
from urllib.parse import urlparse

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[=:]\s*['\"]?[A-Za-z0-9/+_\-]{12,}"),
]
INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts?|rules)"),
    re.compile(r"(?i)disregard (all |any )?(the )?(previous|prior|above)"),
    re.compile(r"(?i)you are now (in )?(dan|developer mode|an? unrestricted)"),
    re.compile(r"(?i)(reveal|print|show|leak) (your |the )?(system prompt|hidden instructions|api key)"),
    re.compile(r"(?i)new instructions?:"),
    re.compile(r"(?i)</?\s*(system|assistant|untrusted)\s*>"),
]


def redact(text: str) -> tuple[str, int]:
    n = 0
    for p in SECRET_PATTERNS:
        text, c = p.subn("[REDACTED]", text)
        n += c
    return text, n


def scan_injection(text: str) -> list[str]:
    return [m.group(0) for p in INJECTION_PATTERNS for m in p.finditer(text)]


def wrap_untrusted(source: str, text: str) -> tuple[str, int]:
    """Neutralise instruction-like content and fence it as data. Returns (block, flagged_count)."""
    flagged = 0
    for p in INJECTION_PATTERNS:
        text, c = p.subn("[removed]", text)
        flagged += c
    text, _ = redact(text)
    src = re.sub(r"[^A-Za-z0-9_:./\-]", "_", source)[:120]
    return f'<untrusted source="{src}">\n{text}\n</untrusted>', flagged


def safe_path(root: str, rel: str) -> Path:
    base = Path(root).resolve()
    base.mkdir(parents=True, exist_ok=True)
    p = (base / rel).resolve()
    if p != base and base not in p.parents:
        raise PermissionError("path escapes sandbox")
    return p


def is_public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    return bool(infos) and all(ipaddress.ip_address(i[4][0]).is_global for i in infos)


def check_url(url: str, allowlist: tuple) -> tuple[bool, str]:
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        return False, "only http/https URLs are allowed"
    if u.port not in (None, 80, 443):
        return False, "port not allowed"
    host = u.hostname.lower()
    if "*" not in allowlist and not any(host == a or host.endswith("." + a) for a in allowlist):
        return False, "host not in allowlist"
    if not is_public_host(host):
        return False, "host is not a public address"
    return True, ""
