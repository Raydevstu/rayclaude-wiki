from fastapi.testclient import TestClient
import hashlib
from pathlib import Path

from tier1.api import create_app
from LAB.repository_adapter import inspect_repository


def payload(**overrides):
    value = {
        "goal": "Review a small change",
        "branch": "main",
        "commit": "unavailable",
        "files": {"LAB/example.txt": "new"},
        "ai_files": ["LAB/example.txt"],
        "protected_user_files": [],
        "baseline_digests": {"LAB/example.txt": "unavailable"},
    }
    value.update(overrides)
    return value


def test_approval_brief_is_read_only_and_exposes_gates(monkeypatch):
    monkeypatch.delenv("TIER1_GUARD_WRITES", raising=False)
    response = TestClient(create_app()).post("/v1/guard/approval", json=payload())
    assert response.status_code == 200
    body = response.json()
    assert body["write_execution"] == "not performed"
    assert body["writes_enabled"] is False
    assert body["approval_required"] is True
    assert "ownership" in body and "rollback" in body and "risks" in body


def test_approval_brief_blocks_path_escape_without_reading_outside(monkeypatch):
    response = TestClient(create_app()).post(
        "/v1/guard/approval", json=payload(
            files={"../outside.txt": "bad"}, ai_files=["../outside.txt"],
            baseline_digests={"../outside.txt": "unavailable"}))
    assert response.status_code == 200
    assert response.json()["status"] == "BLOCKED"
    assert "escapes repository root" in response.json()["risks"][-1]


def test_approval_record_can_be_listed_and_reloaded():
    client = TestClient(create_app())
    created = client.post("/v1/guard/approval", json=payload())
    assert created.status_code == 200
    approval_id = created.json()["approval_id"]
    listed = client.get("/v1/guard/approvals")
    assert listed.status_code == 200
    assert any(row["id"] == approval_id for row in listed.json())
    loaded = client.get(f"/v1/guard/approvals/{approval_id}")
    assert loaded.status_code == 200
    assert loaded.json()["body"]["write_execution"] == "not performed"


def test_explicit_approval_revalidates_identity_and_baseline():
    app = create_app()
    root = Path(__file__).resolve().parent.parent
    repository = inspect_repository(root)
    path = "LAB/README.md"
    digest = hashlib.sha256((root / path).read_bytes()).hexdigest()
    body = {
        "repository": repository.__dict__,
        "files": [{"path": path, "owner": "ai", "proposed": "preview",
                   "baseline_digest": digest}],
        "ownership": {"ai_files": [path], "protected_user_files": []},
        "rollback": {"status": "READY"}, "evidence_level": "local",
        "write_execution": "not performed",
    }
    app.state.svc.store.approval_put("review-1", "REVIEW", body)
    response = TestClient(app).post("/v1/guard/approvals/review-1/approve")
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
    assert app.state.svc.store.approval_get("review-1")["body"]["explicit_approval"] is True
