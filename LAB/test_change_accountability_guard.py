from change_accountability_guard import ChangeAccountabilityContract, ObservedImpact, audit_changes


def test_synthetic_overreach_is_reviewed_with_risks_and_rollback():
    report = audit_changes(
        ChangeAccountabilityContract("add CSV export", ("src/export.py", "tests/test_export.py")),
        (ObservedImpact("src/export.py", ("export_csv",), "CSV export added",
                         dependencies=("shared_formatter",), tests=("unit", "api"), provenance="live"),
         ObservedImpact("auth/middleware.py", ("authorize",), "permission behavior changed",
                         risks=("authorization impact",), provenance="live", rollback="manual review"),
         ObservedImpact("dist/app.js", generated=True, provenance="generated", rollback="rebuild")),
    )
    assert report.status == "REVIEW"
    assert report.unexplained_files == ("auth/middleware.py", "dist/app.js")
    assert "shared_formatter" in report.dependencies
    assert "authorization impact" in report.risks
    assert report.rollback[-1] == "dist/app.js: rebuild"


def test_hypothetical_scoped_change_is_clear():
    report = audit_changes(
        ChangeAccountabilityContract("add CSV export", ("src/export.py", "tests/test_export.py")),
        (ObservedImpact("src/export.py", ("export_csv",), "CSV export added",
                         tests=("unit", "api", "browser"), provenance="live"),
         ObservedImpact("tests/test_export.py", behavior="export acceptance covered",
                         tests=("unit",), provenance="live")),
    )
    assert report.status == "CLEAR"
    assert report.unexplained_files == ()
    assert report.provenance == ("live",)
