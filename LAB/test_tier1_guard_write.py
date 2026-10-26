import hashlib
import os
from pathlib import Path

from fastapi.testclient import TestClient

from tier1.api import create_app
from LAB.repository_adapter import inspect_repository


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def test_guard_write_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TIER1_GUARD_WRITES", raising=False)
    response = TestClient(create_app()).post("/v1/guard/write", json={
        "approval_id": "missing", 
        "approved": True, "branch": "main", "commit": "abc", "files": {"app.py": "new"},
        "ai_files": ["app.py"], "baseline_digests": {"app.py": "old"},
    })
    assert response.status_code == 403


def test_guard_write_requires_explicit_approval(monkeypatch):
    monkeypatch.setenv("TIER1_GUARD_WRITES", "1")
    response = TestClient(create_app()).post("/v1/guard/write", json={
        "approval_id": "missing",
        "approved": False, "branch": "main", "commit": "abc", "files": {"app.py": "new"},
        "ai_files": ["app.py"], "baseline_digests": {"app.py": "old"},
    })
    assert response.status_code == 409


def test_guard_write_rejects_wrong_repository_identity(monkeypatch):
    monkeypatch.setenv("TIER1_GUARD_WRITES", "1")
    response = TestClient(create_app()).post("/v1/guard/write", json={
        "approval_id": "missing",
        "approved": True, "branch": "wrong", "commit": "stale",
        "files": {"LAB/README.md": "not written"}, "ai_files": ["LAB/README.md"],
        "protected_user_files": [], "baseline_digests": {"LAB/README.md": digest("old")},
    })
    assert response.status_code == 404
    assert response.json()["detail"] == "approval record not found"


def _approved_record(app, *, path="LAB/README.md", proposed="not written"):
    root = Path(__file__).resolve().parent.parent
    repository = inspect_repository(root)
    current = (root / path).read_bytes()
    body = {
        "repository": repository.__dict__,
        "files": [{"path": path, "owner": "ai", "proposed": proposed,
                   "baseline_digest": digest(current.decode("utf-8"))}],
        "ownership": {"ai_files": [path], "protected_user_files": []},
        "rollback": {"status": "READY"}, "evidence_level": "local",
        "write_execution": "not performed", "explicit_approval": True,
    }
    app.state.svc.store.approval_put("approved-1", "APPROVED", body)
    return repository, current


def test_guard_write_requires_exact_persisted_proposal(monkeypatch):
    monkeypatch.setenv("TIER1_GUARD_WRITES", "1")
    app = create_app()
    repository, current = _approved_record(app)
    response = TestClient(app).post("/v1/guard/write", json={
        "approval_id": "approved-1", "approved": True,
        "branch": repository.branch, "commit": repository.commit,
        "files": {"LAB/README.md": "different payload"}, "ai_files": ["LAB/README.md"],
        "protected_user_files": [], "baseline_digests": {"LAB/README.md": digest(current.decode())},
    })
    assert response.status_code == 409
    assert "exactly match persisted approval" in response.json()["detail"]


def test_guard_write_rejects_unapproved_persisted_record(monkeypatch):
    monkeypatch.setenv("TIER1_GUARD_WRITES", "1")
    app = create_app()
    client = TestClient(app)
    created = client.post("/v1/guard/approval", json={
        "goal": "test", "branch": "main", "commit": "unavailable",
        "files": {"LAB/example.txt": "new"}, "ai_files": ["LAB/example.txt"],
        "protected_user_files": [], "baseline_digests": {"LAB/example.txt": "missing"},
    })
    approval_id = created.json()["approval_id"]
    response = client.post("/v1/guard/write", json={
        "approval_id": approval_id, "approved": True, "branch": "main", "commit": "unavailable",
        "files": {"LAB/example.txt": "new"}, "ai_files": ["LAB/example.txt"],
        "protected_user_files": [], "baseline_digests": {"LAB/example.txt": "missing"},
    })
    assert response.status_code == 409
    assert "not explicitly approved" in response.json()["detail"]
