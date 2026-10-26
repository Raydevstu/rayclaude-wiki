"""Fail-closed write target for governed local execution."""

from pathlib import Path
import json
import os
import time


MARKER = ".tier1-sandbox"
MANIFEST = ".tier1-sandbox.json"


def resolve_write_root() -> Path:
    """Return only an explicitly provisioned sandbox, never the live checkout."""
    configured = os.environ.get("TIER1_GUARD_SANDBOX_ROOT", "").strip()
    if not configured:
        raise RuntimeError("sandbox write root is not configured")
    root = Path(configured).resolve()
    if not root.is_dir():
        raise RuntimeError("sandbox write root is not a directory")
    marker = root / MARKER
    if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != "tier1-sandbox-v1":
        raise RuntimeError("sandbox write root is not provisioned")
    manifest = root / MANIFEST
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if data.get("version") != "tier1-sandbox-v1" or float(data["expires_at"]) <= time.time():
                raise RuntimeError("sandbox write root has expired")
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("sandbox write root manifest is invalid") from exc
    return root
