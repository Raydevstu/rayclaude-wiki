import hashlib
import subprocess

from fastapi.testclient import TestClient

from tier1.api import create_app
from tier1.sandbox_lifecycle import SandboxLifecycle


def run_git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_approved_write_is_audited_and_rollback_is_verified(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.txt").write_text("before", encoding="utf-8")
    (source / "user.txt").write_text("user", encoding="utf-8")
    run_git(source, "init", "-b", "main")
    run_git(source, "config", "user.email", "test@example.invalid")
    run_git(source, "config", "user.name", "Guard Test")
    run_git(source, "add", ".")
    run_git(source, "commit", "-m", "baseline")
    parent = tmp_path / "sandboxes"
    sandbox = SandboxLifecycle(parent).provision(source, 3600)
    monkeypatch.setenv("TIER1_GUARD_ROOT", str(sandbox.root))
    monkeypatch.setenv("TIER1_GUARD_SANDBOX_ROOT", str(sandbox.root))
    monkeypatch.setenv("TIER1_SANDBOX_PARENT", str(parent))
    monkeypatch.setenv("TIER1_GUARD_WRITES", "1")
    monkeypatch.setenv("TIER1_DB", str(tmp_path.parent / "tier1-e2e.db"))
    app = create_app()
    client = TestClient(app)
    prepared = client.post("/v1/guard/agent/prepare", json={"prompt": "Plan the app content change"})
    assert prepared.status_code == 200
    agent_run_id = prepared.json()["run_id"]
    commit = run_git(sandbox.root, "rev-parse", "--short", "HEAD")
    response = client.post("/v1/guard/approval", json={
        "goal": "Change app content",
        "branch": "main", "commit": commit,
        "files": {"app.txt": "after"}, "ai_files": ["app.txt"],
        "protected_user_files": ["user.txt"],
        "baseline_digests": {"app.txt": digest(sandbox.root / "app.txt"), "user.txt": digest(sandbox.root / "user.txt")},
        "agent_run_id": agent_run_id,
        "sandbox_id": sandbox.sandbox_id,
    })
    assert response.status_code == 200
    approval_id = response.json()["approval_id"]
    assert response.json()["status"] == "REVIEW", response.json()["risks"]
    assert client.post(f"/v1/guard/approvals/{approval_id}/approve").json()["status"] == "APPROVED"

    body = client.get(f"/v1/guard/approvals/{approval_id}").json()["body"]
    write = client.post("/v1/guard/write", json={
        "approval_id": approval_id, "approved": True, "branch": "main", "commit": commit,
        "files": {"app.txt": "after"}, "ai_files": ["app.txt"],
        "protected_user_files": ["user.txt"],
        "baseline_digests": {item["path"]: item["baseline_digest"] for item in body["files"]},
        "agent_run_id": agent_run_id,
        "sandbox_id": sandbox.sandbox_id,
    })
    assert write.status_code == 200
    assert write.json()["status"] == "WRITTEN"
    assert write.json()["post_write_evidence"] is True
    assert (sandbox.root / "app.txt").read_text(encoding="utf-8") == "after"
    audits = client.get(f"/v1/guard/approvals/{approval_id}/audits").json()
    assert audits[0]["action"] == "write"
    assert audits[0]["status"] == "WRITTEN"

    rollback = client.post(f"/v1/guard/approvals/{approval_id}/rollback", json={"approved": True})
    assert rollback.status_code == 200
    assert rollback.json()["status"] == "ROLLED_BACK"
    assert rollback.json()["rollback_evidence"] is True
    assert (sandbox.root / "app.txt").read_text(encoding="utf-8") == "before"
    assert (sandbox.root / "user.txt").read_text(encoding="utf-8") == "user"
    assert client.get(f"/v1/guard/approvals/{approval_id}/audits").json()[0]["action"] == "rollback"


def test_write_rejects_a_different_sandbox_than_the_approved_one(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.txt").write_text("before", encoding="utf-8")
    run_git(source, "init", "-b", "main")
    run_git(source, "config", "user.email", "test@example.invalid")
    run_git(source, "config", "user.name", "Guard Test")
    run_git(source, "add", ".")
    run_git(source, "commit", "-m", "baseline")
    parent = tmp_path / "sandboxes"
    manager = SandboxLifecycle(parent)
    first = manager.provision(source, 3600)
    second = manager.provision(source, 3600)
    monkeypatch.setenv("TIER1_GUARD_ROOT", str(first.root))
    monkeypatch.setenv("TIER1_GUARD_SANDBOX_ROOT", str(first.root))
    monkeypatch.setenv("TIER1_SANDBOX_PARENT", str(parent))
    monkeypatch.setenv("TIER1_GUARD_WRITES", "1")
    monkeypatch.setenv("TIER1_DB", str(tmp_path / "guard.db"))
    client = TestClient(create_app())
    commit = run_git(first.root, "rev-parse", "--short", "HEAD")
    response = client.post("/v1/guard/approval", json={
        "goal": "Change app", "branch": "main", "commit": commit,
        "files": {"app.txt": "after"}, "ai_files": ["app.txt"],
        "baseline_digests": {"app.txt": digest(first.root / "app.txt")},
        "sandbox_id": first.sandbox_id,
    })
    approval_id = response.json()["approval_id"]
    assert client.post(f"/v1/guard/approvals/{approval_id}/approve").status_code == 200
    body = client.get(f"/v1/guard/approvals/{approval_id}").json()["body"]
    rejected = client.post("/v1/guard/write", json={
        "approval_id": approval_id, "sandbox_id": second.sandbox_id, "approved": True,
        "branch": "main", "commit": commit, "files": {"app.txt": "after"},
        "ai_files": ["app.txt"], "baseline_digests": {"app.txt": body["files"][0]["baseline_digest"]},
    })
    assert rejected.status_code == 409
    assert "persisted sandbox" in rejected.json()["detail"]
