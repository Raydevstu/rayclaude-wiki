from task_capsule_guard import TaskCapsuleInput, validate_capsule


def capsule(**overrides):
    values = dict(
        project="Rayclaude-wiki", canonical_sources=("CORE-CREATION.md",), freshness="current",
        goal="continue guard work", implementation_state="LAB guards verified",
        constraints=("keep changes under LAB",), relevant_files=("LAB/",),
        decisions=("use fail-closed validation",), verification=("41 tests passed",),
        next_boundary="build the next guard",
    )
    values.update(overrides)
    return TaskCapsuleInput(**values)


def test_synthetic_stale_conflicting_capsule_is_blocked():
    result, decision = validate_capsule(capsule(
        canonical_sources=("CORE-CREATION.md", "old-handoff.md"), freshness="stale",
        verification=(),
    ))
    assert result is None
    assert decision.status == "BLOCKED"
    assert "conflicting canonical sources" in decision.reasons
    assert "context is stale" in decision.reasons


def test_hypothetical_current_capsule_is_ready():
    result, decision = validate_capsule(capsule())
    assert decision.status == "READY"
    assert result is not None
    assert result.project == "Rayclaude-wiki"
    assert result.version == 1


def test_capsule_carries_repository_identity():
    result, decision = validate_capsule(capsule(
        repository_root="D:/repo", repository_branch="main", repository_commit="abc123",
        repository_dirty=False,
    ))
    assert decision.status == "READY"
    assert result.repository_branch == "main"
    assert result.repository_commit == "abc123"
    assert result.repository_dirty is False
