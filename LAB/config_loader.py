"""Small, explicit configuration loader for guard thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class GuardConfig:
    max_files: int = 20
    max_changed_lines: int = 1000
    risk: str = "low"


def load_guard_config(path: str | Path | None = None) -> GuardConfig:
    if path is None:
        return GuardConfig()
    file = Path(path)
    if not file.is_file():
        raise ValueError(f"configuration file not found: {file}")
    try:
        raw = tomllib.loads(file.read_text(encoding="utf-8"))
        values = raw.get("scope", raw)
        result = GuardConfig(int(values.get("max_files", 20)),
                             int(values.get("max_changed_lines", 1000)),
                             str(values.get("risk", "low")))
    except (OSError, ValueError, TypeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid guard configuration: {file}") from exc
    if result.max_files < 0 or result.max_changed_lines < 0 or result.risk not in {"low", "medium", "high"}:
        raise ValueError("invalid guard thresholds or risk")
    return result
