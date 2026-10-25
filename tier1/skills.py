from __future__ import annotations
import math
from dataclasses import dataclass, field
from pathlib import Path

from .safety import scan_injection
from .util import tok, words


@dataclass
class Skill:
    name: str
    description: str = ""
    triggers: list = field(default_factory=list)
    priority: int = 1
    instructions: str = ""
    path: str = ""


def _parse(text: str, path: str) -> Skill:
    if not text.startswith("---"):
        raise ValueError("missing frontmatter")
    head, _, body = text[3:].partition("\n---")
    meta = {}
    for line in head.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    if not meta.get("name"):
        raise ValueError("missing name")
    trig = [t.strip().lower() for t in meta.get("triggers", "").strip("[]").split(",") if t.strip()]
    try:
        prio = int(meta.get("priority", 1))
    except ValueError:
        prio = 1
    return Skill(meta["name"], meta.get("description", ""), trig, prio, body.strip(), path)


class SkillRegistry:
    """Loads skills from *.md manifests; hot-reloads when files change (auto-import)."""

    def __init__(self, directory: str):
        self.dir, self.skills, self.errors, self.signature = Path(directory), {}, {}, ""
        self.refresh()

    def _sig(self) -> str:
        if not self.dir.is_dir():
            return "none"
        return "|".join(f"{p.name}:{p.stat().st_mtime_ns}" for p in sorted(self.dir.glob("*.md")))

    def refresh(self) -> bool:
        sig = self._sig()
        if sig == self.signature:
            return False
        self.signature, self.skills, self.errors = sig, {}, {}
        for p in sorted(self.dir.glob("*.md")) if self.dir.is_dir() else []:
            try:
                s = _parse(p.read_text(), str(p))
                if scan_injection(s.instructions):
                    raise ValueError("skill contains instruction-override patterns")
                self.skills[s.name] = s
            except (ValueError, OSError) as e:
                self.errors[p.name] = str(e)
        return True

    def match(self, text: str, k: int = 3, budget: int = 600) -> list[tuple[Skill, float]]:
        self.refresh()
        low, qw = text.lower(), set(words(text))
        docs = {n: set(words(" ".join(s.triggers) + " " + s.description)) for n, s in self.skills.items()}
        N = max(1, len(docs))
        df: dict[str, int] = {}
        for d in docs.values():
            for w in d:
                df[w] = df.get(w, 0) + 1
        scored = []
        for n, s in self.skills.items():
            sc = sum((3.0 if " " in t else 2.0) for t in s.triggers if t in low)
            sc += 0.5 * sum(math.log(1 + N / df[w]) for w in qw & docs[n])
            if sc >= 2.0:
                scored.append((s, sc * (1 + 0.1 * s.priority)))
        scored.sort(key=lambda x: -x[1])
        out, used = [], 0
        for s, sc in scored[:k]:
            t = tok(s.instructions)
            if used + t <= budget:
                out.append((s, sc))
                used += t
        return out

    def all_instruction_tokens(self) -> int:
        return sum(tok(s.instructions) for s in self.skills.values())
