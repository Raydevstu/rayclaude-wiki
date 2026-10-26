from pathlib import Path
from hashlib import sha256

from rollback_guard import FileOwnership, OwnershipConfirmation, plan_rollback
from sandboxed_write_executor import execute_sandboxed_write


def _plan():
    return plan_rollback((
        FileOwnership("app.py", sha256(b"old").hexdigest(), "new", "ai"),
        FileOwnership("notes.md", sha256(b"user-old").hexdigest(), "user-new", "user"),
    ))


def _confirmation():
    return OwnershipConfirmation("abc", "main", ("app.py",), ("notes.md",))


def test_writes_only_confirmed_ai_file_and_preserves_user_file(tmp_path: Path):
    (tmp_path / "app.py").write_text("old", encoding="utf-8")
    (tmp_path / "notes.md").write_text("user-new", encoding="utf-8")
    result = execute_sandboxed_write(tmp_path, {"app.py": "new"}, rollback=_plan(),
                                     ownership=_confirmation(), repository_commit="abc",
                                     repository_branch="main")
    assert result.status == "WRITTEN"
    assert result.changed_files == ("app.py",)
    assert (tmp_path / "notes.md").read_text(encoding="utf-8") == "user-new"


def test_rejects_missing_or_mismatched_ownership_before_writing(tmp_path: Path):
    (tmp_path / "app.py").write_text("old", encoding="utf-8")
    result = execute_sandboxed_write(tmp_path, {"app.py": "new"}, rollback=_plan(),
                                     ownership=None, repository_commit="abc",
                                     repository_branch="main")
    assert result.status == "BLOCKED"
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "old"


def test_rejects_user_file_and_path_escape(tmp_path: Path):
    result = execute_sandboxed_write(tmp_path, {"notes.md": "overwrite"}, rollback=_plan(),
                                     ownership=_confirmation(), repository_commit="abc",
                                     repository_branch="main")
    assert result.status == "BLOCKED"
    result = execute_sandboxed_write(tmp_path, {"app.py": "new", "../escape.py": "bad"},
                                     rollback=_plan(), ownership=_confirmation(),
                                     repository_commit="abc", repository_branch="main")
    assert result.status == "BLOCKED"


def test_rejects_wrong_repository_identity(tmp_path: Path):
    result = execute_sandboxed_write(tmp_path, {"app.py": "new"}, rollback=_plan(),
                                     ownership=_confirmation(), repository_commit="stale",
                                     repository_branch="main")
    assert result.status == "BLOCKED"


def test_rejects_baseline_drift_before_writing(tmp_path: Path):
    target = tmp_path / "app.py"
    target.write_text("user-edited", encoding="utf-8")
    plan = plan_rollback((FileOwnership(
        "app.py", "0" * 64, "new", "ai"),))
    confirmation = OwnershipConfirmation("abc", "main", ("app.py",))
    result = execute_sandboxed_write(tmp_path, {"app.py": "new"}, rollback=plan,
                                     ownership=confirmation, repository_commit="abc",
                                     repository_branch="main")
    assert result.status == "BLOCKED"
    assert target.read_text(encoding="utf-8") == "user-edited"
