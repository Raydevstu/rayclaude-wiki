from rollback_guard import FileOwnership, OwnershipConfirmation, ownership_mismatch, plan_rollback


def test_synthetic_rollback_protects_user_changes_and_limits_boundary():
    plan = plan_rollback((
        FileOwnership("src/app.py", "old", "ai", "ai"),
        FileOwnership("README.md", "user-old", "user-new", "user"),
    ))
    assert plan.status == "READY"
    assert plan.boundary == ("src/app.py",)
    assert plan.protected_user_files == ("README.md",)


def test_destructive_or_external_effect_requires_confirmation():
    plan = plan_rollback((FileOwnership("db/migration.sql", "old", "new", "ai", False),))
    assert plan.status == "BLOCKED"
    assert "db/migration.sql" in plan.irreversible


def test_ownership_confirmation_matches_rollback_boundary():
    plan = plan_rollback((
        FileOwnership("app.py", "old", "new", "ai"),
        FileOwnership("notes.md", "old", "new", "user"),
    ))
    confirmation = OwnershipConfirmation("abc", "main", ("app.py",), ("notes.md",))
    assert ownership_mismatch(plan, confirmation, repository_commit="abc", repository_branch="main") is None
