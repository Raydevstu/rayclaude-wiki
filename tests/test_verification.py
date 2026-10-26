from tier1.verification import evaluate_acceptance


def test_no_acceptance_criteria_is_unverified():
    result = evaluate_acceptance("Anything", None)
    assert result["status"] == "unverified"


def test_exact_answer_is_verified_after_normalization():
    result = evaluate_acceptance("  READY\n", {"equals": "ready"})
    assert result["status"] == "verified"


def test_missing_required_term_fails_verification():
    result = evaluate_acceptance("Contains alpha only", {"contains_all": ["alpha", "beta"]})
    assert result["status"] == "failed_verification"
    assert result["checks"]["contains_all"]["missing"] == ["beta"]


def test_missing_json_key_fails_verification():
    result = evaluate_acceptance('{"answer": "ok"}', {"json_required_keys": ["answer", "citations"]})
    assert result["status"] == "failed_verification"
    assert result["checks"]["json_required_keys"]["missing"] == ["citations"]
