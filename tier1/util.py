from __future__ import annotations
import hashlib, math, re

_W = re.compile(r"[a-z0-9_]{2,}")
STOP = {"the", "and", "for", "with", "that", "this", "from", "are", "was", "you", "your", "have",
        "has", "into", "about", "what", "how", "can", "will"}


def tok(text: str) -> int:
    """Rough token estimate (chars/4). Used for budgeting and baselines only; billing uses provider usage."""
    return max(1, math.ceil(len(text) / 4))


def words(text: str) -> list[str]:
    return [w for w in _W.findall(text.lower()) if w not in STOP]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def extractive(text: str, query: str, budget: int) -> str:
    """Keep the sentences most relevant to `query` within a token budget (deterministic compression)."""
    if tok(text) <= budget:
        return text
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]
    q = set(words(query))
    order = sorted(range(len(parts)), key=lambda i: (-(len(q & set(words(parts[i]))) + 1.0 / (1 + i)), i))
    keep, used = [], 0
    for i in order:
        t = tok(parts[i])
        if used + t <= budget:
            keep.append(i)
            used += t
    if not keep:
        return text[: budget * 4]
    return " ".join(parts[i] for i in sorted(keep))


def rank(query: str, docs: list[str], k: int = 3) -> list[tuple[int, float]]:
    """IDF-weighted overlap ranking. Returns [(doc_index, score)] for score > 0."""
    qs = set(words(query))
    sets = [set(words(d)) for d in docs]
    n = len(docs) or 1
    df: dict[str, int] = {}
    for s in sets:
        for w in s:
            df[w] = df.get(w, 0) + 1
    out = []
    for i, s in enumerate(sets):
        sc = sum(math.log(1 + n / df[w]) for w in qs & s) / math.sqrt(len(s) + 1)
        if sc > 0:
            out.append((i, sc))
    return sorted(out, key=lambda x: -x[1])[:k]
