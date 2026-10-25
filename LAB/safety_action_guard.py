"""Fail-closed authorization checks for AI-generated actions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionRequest:
    action: str
    target: str
    permission: str
    destructive: bool = False
    external_content: bool = False
    secret_data: bool = False
    transmit_data: bool = False
    approved_transmission: bool = False
    confirmed: bool = False
    input_valid: bool = True
    output_valid: bool = True
    reversible: bool = True


@dataclass(frozen=True)
class SafetyDecision:
    status: str
    reasons: tuple[str, ...]
    recommendation: str


def authorize_action(request: ActionRequest) -> SafetyDecision:
    """Return ALLOW only when the supplied action passes every safety gate."""
    reasons: list[str] = []
    if request.external_content:
        reasons.append("external content is untrusted")
    if request.permission not in {"read", "write", "approved-destructive"}:
        reasons.append("permission is not authorized")
    if request.destructive and not request.confirmed:
        reasons.append("destructive confirmation required")
    if request.secret_data and request.transmit_data and not request.approved_transmission:
        reasons.append("secret transmission is not approved")
    if not request.input_valid:
        reasons.append("input validation failed")
    if not request.output_valid:
        reasons.append("output validation failed")
    if not request.reversible and not request.confirmed:
        reasons.append("irreversible action requires confirmation")
    if reasons:
        return SafetyDecision("BLOCKED", tuple(reasons), "do not execute; resolve safety findings")
    return SafetyDecision("ALLOW", (), "execute within the approved boundary")
