from maintainability_guard import MaintainabilityInput, evaluate_maintainability


def test_synthetic_maintainability_debt_is_blocked_or_reviewed():
    report = evaluate_maintainability(MaintainabilityInput(
        patterns_reused=False,
        unnecessary_abstraction=True,
        duplication=True,
        boundary_violation=True,
        focused_tests=False,
        complexity=True,
        decision_record_needed=True,
        dependency_concern=True,
        findings=("existing CSV helper already exists",),
    ))
    assert report.status == "BLOCKED"
    assert "duplication detected" in report.findings
    assert "focused tests missing" in report.findings
    assert "existing CSV helper already exists" in report.findings


def test_hypothetical_pattern_consistent_change_is_clear():
    report = evaluate_maintainability(MaintainabilityInput(
        patterns_reused=True,
        focused_tests=True,
    ))
    assert report.status == "CLEAR"
    assert report.findings == ()
