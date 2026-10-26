from hashlib import sha256
from pathlib import Path

from rollback_guard import FileOwnership, OwnershipConfirmation, plan_rollback
from sandboxed_write_executor import execute_sandboxed_rollback


def digest(text: str) -> str:
    return sha256(text.encode()).hexdigest()


def test_rollback_restores_ai_file_and_preserves_user_file(tmp_path: Path):
    (tmp_path / "app.py").write_text("new", encoding="utf-8")
    (tmp_path / "notes.md").write_text("user", encoding="utf-8")
    plan = plan_rollback((FileOwnership("app.py", digest("old"), digest("new"), "ai"),
                          FileOwnership("notes.md", digest("user"), digest("user"), "user")))
    result = execute_sandboxed_rollback(
        tmp_path, {"app.py": "old"}, expected_current_digests={"app.py": digest("new")},
        protected_user_digests={"notes.md": digest("user")}, rollback=plan,
        ownership=OwnershipConfirmation("abc", "main", ("app.py",), ("notes.md",)),
        repository_commit="abc", repository_branch="main")
    assert result.status == "ROLLED_BACK"
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "old"
    assert (tmp_path / "notes.md").read_text(encoding="utf-8") == "user"


def test_rollback_refuses_changed_user_file(tmp_path: Path):
    (tmp_path / "app.py").write_text("new", encoding="utf-8")
    (tmp_path / "notes.md").write_text("user-changed", encoding="utf-8")
    plan = plan_rollback((FileOwnership("app.py", digest("old"), digest("new"), "ai"),
                          FileOwnership("notes.md", digest("user"), digest("user"), "user")))
    result = execute_sandboxed_rollback(
        tmp_path, {"app.py": "old"}, expected_current_digests={"app.py": digest("new")},
        protected_user_digests={"notes.md": digest("user")}, rollback=plan,
        ownership=OwnershipConfirmation("abc", "main", ("app.py",), ("notes.md",)),
        repository_commit="abc", repository_branch="main")
    assert result.status == "BLOCKED"
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "new"
