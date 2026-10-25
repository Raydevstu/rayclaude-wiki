from pathlib import Path

from scope_guard import (
    ChangeContract,
    ChangedFile,
    changed_files,
    evaluate,
    expansion_request,
    snapshot_workspace,
)


def test_passes_when_change_stays_inside_contract():
    contract = ChangeContract(
        goal="add export",
        allowed_files=("src/export.py", "tests/test_export.py"),
        allowed_layers=("utility", "test"),
        acceptance_tests=("export works",),
    )
    result = evaluate(contract, [
        ChangedFile("src/export.py", 20, "utility"),
        ChangedFile("tests/test_export.py", 12, "test"),
    ])
    assert result.status == "PASS"
    assert result.unexpected_changes == ()


def test_requests_review_for_unexpected_scope():
    contract = ChangeContract(goal="add export", allowed_files=("src/export.py",))
    result = evaluate(contract, [ChangedFile("src/export.py", 10), ChangedFile("src/auth.py", 4)])
    assert result.status == "REVIEW"
    assert result.unexpected_changes == ("src/auth.py",)


def test_blocks_budget_and_destructive_changes():
    contract = ChangeContract(goal="migrate data", max_files=1, max_changed_lines=5)
    result = evaluate(contract, [ChangedFile("db/migrate.sql", 8, destructive=True)])
    assert result.status == "BLOCKED"
    assert result.rollback_available is False


def test_expansion_requires_reason():
    contract = ChangeContract(goal="add export", allowed_files=("src/export.py",))
    request = expansion_request(contract, ChangedFile("src/api.py", layer="api"), "API must expose export")
    assert request["status"] == "approval_required"
    assert request["requested_file"] == "src/api.py"


def test_real_workspace_snapshot_detects_unrelated_and_destructive_changes(tmp_path: Path):
    (tmp_path / "components").mkdir()
    (tmp_path / "auth").mkdir()
    (tmp_path / "db").mkdir()
    (tmp_path / "components" / "export.tsx").write_text("button", encoding="utf-8")
    before = snapshot_workspace(tmp_path)

    (tmp_path / "components" / "export.tsx").write_text("button\ndownload", encoding="utf-8")
    (tmp_path / "auth" / "middleware.ts").write_text("changed", encoding="utf-8")
    (tmp_path / "db" / "migration.sql").write_text("DROP TABLE users", encoding="utf-8")
    after = snapshot_workspace(tmp_path)

    changes = changed_files(before, after)
    result = evaluate(ChangeContract(
        goal="add export",
        allowed_files=("components/export.tsx",),
        allowed_layers=("ui",),
        max_files=2,
        max_changed_lines=10,
        acceptance_tests=("download works",),
    ), changes)
    assert {change.path for change in changes} == {
        "auth/middleware.ts", "components/export.tsx", "db/migration.sql"
    }
    assert result.status == "BLOCKED"
    assert "auth/middleware.ts" in result.unexpected_changes
    assert "db/migration.sql" in result.unexpected_changes
    assert result.rollback_available is False
