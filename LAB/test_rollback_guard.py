from rollback_guard import FileOwnership, plan_rollback


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
