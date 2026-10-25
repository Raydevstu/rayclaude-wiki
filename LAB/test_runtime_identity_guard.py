from runtime_identity_guard import RuntimeContract, RuntimeEvidence, inspect_runtime


def contract():
    return RuntimeContract("Rayclaude-wiki", "abc123", 8000, "/", "Tier-1 Control Plane")


def test_wrong_process_is_unverified_even_when_port_responds():
    result = inspect_runtime(contract(), RuntimeEvidence(
        "Other-app", "old", 8080, "/", "Context Governor", 200, True
    ))
    assert result.status == "UNVERIFIED"
    assert "wrong project" in result.mismatches
    assert "wrong port" in result.mismatches
    assert "do not edit" in result.recommendation


def test_matching_runtime_is_ready():
    result = inspect_runtime(contract(), RuntimeEvidence(
        "Rayclaude-wiki", "abc123", 8000, "/", "Tier-1 Control Plane", 200, True
    ))
    assert result.status == "READY"
    assert result.mismatches == ()


def test_http_200_without_readiness_is_not_verified():
    result = inspect_runtime(contract(), RuntimeEvidence(
        "Rayclaude-wiki", "abc123", 8000, "/", "Tier-1 Control Plane", 200, False
    ))
    assert result.status == "UNVERIFIED"
    assert "runtime not ready" in result.mismatches


def test_synthetic_wrong_runtime_is_blocked_from_code_repair():
    result = inspect_runtime(contract(), RuntimeEvidence(
        "Context-Governor", "old999", 8080, "/dashboard", "Context Governor", 200, True
    ))
    assert result.status == "UNVERIFIED"
    assert set(result.mismatches) >= {"wrong project", "wrong port", "wrong page title"}
    assert result.recommendation.startswith("do not edit")


def test_hypothetical_intended_launch_is_ready():
    result = inspect_runtime(contract(), RuntimeEvidence(
        "Rayclaude-wiki", "abc123", 8000, "/", "Tier-1 Control Plane", 200, True
    ))
    assert result.status == "READY"
    assert result.recommendation == "safe to continue with the verified runtime"
