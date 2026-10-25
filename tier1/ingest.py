"""Turn fetched or uploaded documents into indexable text (HTML, PDF, plain text/Markdown/JSON/CSV)."""
from __future__ import annotations
import html, io, re
from html.parser import HTMLParser
from pathlib import Path

SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "template"}
BLOCK = {"p", "div", "br", "li", "tr", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote", "table"}
TEXT_TYPES = (".md", ".markdown", ".txt", ".csv", ".json", ".log", ".rst")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.title, self._in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in BLOCK:
            self.out.append("\n\n" if tag[0] in "hpd" or tag in ("section", "article", "pre") else "\n")
            if tag[0] == "h" and len(tag) == 2:
                self.out.append("#" * int(tag[1]) + " ")

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.out.append(data)


def html_to_text(raw: str) -> tuple[str, str]:
    p = _Text()
    p.feed(raw[:3_000_000])
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.out))
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return html.unescape(p.title).strip()[:200], text


def pdf_to_text(data: bytes, max_pages: int = 300) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ValueError("PDF support needs the optional dependency: pip install 'tier1-agent[pdf]'")
    try:
        r = PdfReader(io.BytesIO(data))
        if r.is_encrypted:
            raise ValueError("encrypted PDFs are not supported")
        pages = [(p.extract_text() or "") for p in r.pages[:max_pages]]
    except ValueError:
        raise
    except Exception as e:                       # malformed input must not crash the worker
        raise ValueError(f"could not read PDF ({type(e).__name__})")
    text = "\n\n".join(x.strip() for x in pages if x.strip())
    if not text:
        raise ValueError("PDF has no extractable text (scanned images need OCR, which is not included)")
    return text


def extract(data: bytes, ctype: str = "", name: str = "") -> tuple[str, str]:
    """Return (title, text). Dispatch on content type first, then file extension; refuse unknown binary formats."""
    ctype, ext = (ctype or "").lower(), Path(name.split("?")[0]).suffix.lower()
    if "pdf" in ctype or ext == ".pdf" or data[:5] == b"%PDF-":
        return Path(name).stem[:200], pdf_to_text(data)
    if "html" in ctype or ext in (".html", ".htm") or data[:200].lstrip().lower().startswith((b"<!doctype html", b"<html")):
        return html_to_text(data.decode("utf-8", "replace"))
    if ctype.startswith("text/") or "json" in ctype or "xml" in ctype or ext in TEXT_TYPES:
        if b"\x00" in data[:2000]:
            raise ValueError("binary content")
        return "", data.decode("utf-8", "replace")
    raise ValueError(f"unsupported content type {ctype or ext or 'unknown'!r} (supported: HTML, PDF, text, Markdown, JSON, CSV)")
