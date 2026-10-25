from safety_action_guard import ActionRequest, authorize_action


def test_synthetic_adversarial_action_is_blocked():
    result = authorize_action(ActionRequest(
        "run migration", "production-db", "write", destructive=True,
        external_content=True, secret_data=True, transmit_data=True,
        input_valid=False, reversible=False,
    ))
    assert result.status == "BLOCKED"
    assert "external content is untrusted" in result.reasons
    assert "destructive confirmation required" in result.reasons
    assert "secret transmission is not approved" in result.reasons


def test_hypothetical_scoped_read_action_is_allowed():
    result = authorize_action(ActionRequest(
        "read source file", "LAB/guard.py", "read", input_valid=True, output_valid=True,
    ))
    assert result.status == "ALLOW"
    assert result.reasons == ()
