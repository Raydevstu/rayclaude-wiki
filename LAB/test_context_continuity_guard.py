from context_continuity_guard import ContextSource, build_context_capsule


def source(name="CORE.md", project="demo", authority="canonical", freshness="current"):
    return ContextSource(name, project, authority, freshness, ("decision: use LAB",))


def test_builds_verified_capsule_from_current_canonical_context():
    capsule, report = build_context_capsule("demo", (source(),), "implement the next LAB slice")
    assert report.status == "READY"
    assert capsule is not None
    assert capsule.authoritative_sources == ("CORE.md",)


def test_blocks_stale_context_and_does_not_guess():
    capsule, report = build_context_capsule("demo", (source(freshness="stale"),), "continue")
    assert capsule is None
    assert report.status == "BLOCKED"
    assert report.stale_sources == ("CORE.md",)


def test_blocks_identity_conflict_and_missing_boundary():
    capsule, report = build_context_capsule(
        "demo", (source(), source("other.md", project="other")), ""
    )
    assert capsule is None
    assert report.status == "BLOCKED"
    assert "continuation boundary" in report.missing
    assert any("identity mismatch" in item for item in report.conflicts)


def test_synthetic_adversarial_context_is_blocked():
    """Synthetic history contains stale and contradictory project sources."""
    capsule, report = build_context_capsule(
        "rayclaude-wiki",
        (source("CORE-CREATION.md", "rayclaude-wiki"),
         source("old-handoff.md", "rayclaude-wiki", freshness="stale"),
         source("other-project.md", "other-project")),
        "continue Scope Guard work",
    )
    assert capsule is None
    assert report.status == "BLOCKED"
    assert report.stale_sources == ("old-handoff.md",)
    assert any("identity mismatch" in item for item in report.conflicts)


def test_hypothetical_new_session_creates_safe_handoff_capsule():
    """A new session receives current canonical facts and an explicit next step."""
    capsule, report = build_context_capsule(
        "rayclaude-wiki",
        (ContextSource("CORE-CREATION.md", "rayclaude-wiki", "canonical", "current",
                       ("LAB guards verified", "next: add repository adapter")),),
        "implement the read-only repository adapter under LAB",
    )
    assert report.status == "READY"
    assert capsule is not None
    assert capsule.next_boundary.startswith("implement")
    assert "LAB guards verified" in capsule.facts
