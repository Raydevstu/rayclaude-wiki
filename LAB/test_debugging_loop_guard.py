from debugging_loop_guard import DebugAttempt, evaluate_attempt


def attempt(**overrides):
    values = {
        "failure": "browser blank",
        "reproduction": "open /",
        "evidence": ("console error",),
        "hypothesis": "missing route",
        "changed_files": ("app/routes.py",),
        "result": "fixed",
    }
    values.update(overrides)
    return DebugAttempt(**values)


def test_verified_fix_is_retained():
    result = evaluate_attempt(attempt())
    assert (result.status, result.decision) == ("VERIFIED", "retain")


def test_repeated_hypothesis_is_blocked():
    result = evaluate_attempt(attempt(), (attempt(),))
    assert result.status == "BLOCKED"
    assert result.decision == "escalate"


def test_regression_requires_revert():
    result = evaluate_attempt(attempt(regression=True))
    assert (result.status, result.decision) == ("REVIEW", "revert")


def test_failed_attempt_is_superseded():
    result = evaluate_attempt(attempt(result="failed"))
    assert (result.status, result.decision) == ("REVIEW", "supersede")


def test_missing_evidence_is_blocked():
    result = evaluate_attempt(attempt(evidence=()))
    assert result.status == "BLOCKED"


def test_synthetic_adversarial_loop_blocks_repeated_unproven_fix():
    previous = (attempt(result="failed"),)
    result = evaluate_attempt(attempt(result="failed"), previous)
    assert result.status == "BLOCKED"
    assert result.decision == "escalate"
    assert "already attempted" in result.reason


def test_hypothetical_browser_fix_is_retained_only_after_verification():
    result = evaluate_attempt(DebugAttempt(
        failure="blank browser page",
        reproduction="launch app and open /",
        evidence=("page title missing", "route trace collected"),
        hypothesis="root route is not registered",
        changed_files=("app/routes.py",),
        result="fixed",
        regression=False,
    ))
    assert result.status == "VERIFIED"
    assert result.decision == "retain"
