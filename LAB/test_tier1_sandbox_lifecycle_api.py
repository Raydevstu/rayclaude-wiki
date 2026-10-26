import threading
import time

from fastapi.testclient import TestClient

from tier1.api import create_app
from tier1.sandbox_lifecycle import SandboxLifecycle


def test_sandbox_lifecycle_api_provisions_and_requires_force_for_early_cleanup(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.txt").write_text("before", encoding="utf-8")
    monkeypatch.setenv("TIER1_SANDBOX_PARENT", str(tmp_path / "sandboxes"))
    monkeypatch.setenv("TIER1_GUARD_ROOT", str(source))
    client = TestClient(create_app())
    created = client.post("/v1/guard/sandboxes", json={"ttl_seconds": 60})
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    assert created.json()["status"] in {"QUEUED", "PROVISIONING", "READY"}
    for _ in range(500):
        status = client.get(f"/v1/guard/sandboxes/jobs/{job_id}")
        if status.json()["status"] == "READY":
            break
        time.sleep(0.02)
    assert status.json()["status"] == "READY"
    sandbox_id = status.json()["sandbox_id"]
    listed = client.get("/v1/guard/sandboxes")
    assert listed.status_code == 200
    item = next(x for x in listed.json()["sandboxes"] if x["sandbox_id"] == sandbox_id)
    assert item["status"] == "READY"
    assert item["repository"]["branch"] == "main"
    detail = client.get(f"/v1/guard/sandboxes/{sandbox_id}")
    assert detail.status_code == 200
    assert detail.json()["root"].endswith(sandbox_id)
    early = client.delete(f"/v1/guard/sandboxes/{sandbox_id}")
    assert early.status_code == 202
    early_job = early.json()["job_id"]
    for _ in range(500):
        cleanup_status = client.get(f"/v1/guard/sandboxes/jobs/{early_job}")
        if cleanup_status.json()["status"] == "FAILED":
            break
        time.sleep(0.02)
    assert cleanup_status.json()["status"] == "FAILED"
    assert "not expired" in cleanup_status.json()["reason"]
    removed = client.delete(f"/v1/guard/sandboxes/{sandbox_id}?force=true")
    assert removed.status_code == 202
    cleanup_job = removed.json()["job_id"]
    for _ in range(500):
        cleanup_status = client.get(f"/v1/guard/sandboxes/jobs/{cleanup_job}")
        if cleanup_status.json()["status"] == "REMOVED":
            break
        time.sleep(0.02)
    assert cleanup_status.json()["status"] == "REMOVED"


def test_sandbox_provision_job_can_be_cancelled_and_partial_state_is_not_listed(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.txt").write_text("before", encoding="utf-8")
    monkeypatch.setenv("TIER1_SANDBOX_PARENT", str(tmp_path / "sandboxes"))
    monkeypatch.setenv("TIER1_GUARD_ROOT", str(source))
    started = threading.Event()
    release = threading.Event()
    original = SandboxLifecycle.provision

    def blocked(manager, source_path, ttl_seconds=3600, *, cancel_event=None, progress=None):
        started.set()
        while not release.is_set():
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("sandbox provisioning cancelled")
            time.sleep(0.005)
        return original(manager, source_path, ttl_seconds, cancel_event=cancel_event, progress=progress)

    monkeypatch.setattr(SandboxLifecycle, "provision", blocked)
    client = TestClient(create_app())
    created = client.post("/v1/guard/sandboxes", json={"ttl_seconds": 60})
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    assert started.wait(1)
    cancelled = client.delete(f"/v1/guard/sandboxes/jobs/{job_id}")
    assert cancelled.status_code == 202
    release.set()
    for _ in range(100):
        status = client.get(f"/v1/guard/sandboxes/jobs/{job_id}")
        if status.json()["status"] == "CANCELLED":
            break
        time.sleep(0.01)
    assert status.json()["status"] == "CANCELLED"
    assert client.get("/v1/guard/sandboxes").json()["sandboxes"] == []
