"""Deterministic acceptance checks for task output."""
from __future__ import annotations

import json


def _normalise(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def evaluate_acceptance(answer: str, acceptance: dict | None) -> dict:
    """Return explicit verification evidence; absence of checks is never success."""
    if not acceptance:
        return {"status": "unverified", "checks": {}}
    checks: dict[str, dict] = {}
    passed = True
    if "equals" in acceptance:
        expected = str(acceptance["equals"])
        ok = _normalise(answer) == _normalise(expected)
        checks["equals"] = {"ok": ok, "expected": expected}
        passed &= ok
    if "contains_all" in acceptance:
        required = [str(item) for item in acceptance["contains_all"]]
        actual = answer.casefold()
        missing = [item for item in required if item.casefold() not in actual]
        checks["contains_all"] = {"ok": not missing, "missing": missing}
        passed &= not missing
    if "json_required_keys" in acceptance:
        required = [str(item) for item in acceptance["json_required_keys"]]
        try:
            payload = json.loads(answer)
            missing = [item for item in required if not isinstance(payload, dict) or item not in payload]
        except (TypeError, json.JSONDecodeError):
            missing = required
        checks["json_required_keys"] = {"ok": not missing, "missing": missing}
        passed &= not missing
    return {"status": "verified" if passed else "failed_verification", "checks": checks}
