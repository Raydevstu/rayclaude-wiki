import json
import time

import pytest

from tier1.sandbox_lifecycle import SandboxJobManager, SandboxLifecycle
from tier1.store import Store


def test_lifecycle_provisions_git_sandbox_and_refuses_early_cleanup(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.txt").write_text("before", encoding="utf-8")
    manager = SandboxLifecycle(tmp_path / "sandboxes")
    record = manager.provision(source, ttl_seconds=60)
    assert (record.root / ".tier1-sandbox").read_text().strip() == "tier1-sandbox-v1"
    assert (record.root / "app.txt").read_text() == "before"
    assert (record.root / ".git").is_dir()
    with pytest.raises(ValueError, match="not expired"):
        manager.cleanup(record.sandbox_id)
    assert manager.cleanup(record.sandbox_id, force=True)
    assert not record.root.exists()


def test_lifecycle_cleans_only_expired_managed_sandboxes(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.txt").write_text("before", encoding="utf-8")
    manager = SandboxLifecycle(tmp_path / "sandboxes")
    record = manager.provision(source, ttl_seconds=60)
    manifest = record.root / ".tier1-sandbox.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["expires_at"] = 0
    manifest.write_text(json.dumps(data), encoding="utf-8")
    (manager.parent / "unmanaged").mkdir()
    assert manager.cleanup_expired() == [record.sandbox_id]
    assert (manager.parent / "unmanaged").is_dir()


def test_sandbox_jobs_survive_manager_restart_and_expiry_sweep_uses_manifests(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.txt").write_text("before", encoding="utf-8")
    parent = tmp_path / "sandboxes"
    store = Store(str(tmp_path / "state.db"))
    first = SandboxJobManager(SandboxLifecycle(parent), store)
    job = first.provision(source, 60)
    for _ in range(200):
        restored = first.get(job["job_id"])
        if restored["status"] == "READY":
            break
        time.sleep(0.01)
    assert restored["status"] == "READY"
    second = SandboxJobManager(SandboxLifecycle(parent), store)
    assert second.get(job["job_id"])["sandbox_id"] == restored["sandbox_id"]
    manifest = parent / restored["sandbox_id"] / ".tier1-sandbox.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["expires_at"] = 0
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert second.lifecycle.cleanup_expired() == [restored["sandbox_id"]]


def test_sandbox_job_restart_marks_inflight_work_interrupted(tmp_path):
    store = Store(str(tmp_path / "state.db"))
    store.sandbox_job_put("job-1", "PROVISIONING", {"job_id": "job-1", "status": "PROVISIONING"})
    manager = SandboxJobManager(SandboxLifecycle(tmp_path / "sandboxes"), store)
    job = manager.get("job-1")
    assert job["status"] == "FAILED"
    assert job["reason"] == "interrupted by process restart"


def test_sandbox_job_retention_prunes_old_terminal_jobs(tmp_path):
    store = Store(str(tmp_path / "state.db"))
    for index in range(3):
        store.sandbox_job_put(f"job-{index}", "READY", {"job_id": f"job-{index}", "status": "READY"})
    manager = SandboxJobManager(SandboxLifecycle(tmp_path / "sandboxes"), store, max_retained_jobs=2)
    assert [job["job_id"] for job in store.sandbox_jobs_list()] == ["job-1", "job-2"]


def test_concurrent_cleanup_requests_do_not_run_same_sandbox_twice(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.txt").write_text("before", encoding="utf-8")
    lifecycle = SandboxLifecycle(tmp_path / "sandboxes")
    record = lifecycle.provision(source, ttl_seconds=60)
    manifest = record.root / ".tier1-sandbox.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["expires_at"] = 0
    manifest.write_text(json.dumps(data), encoding="utf-8")
    manager = SandboxJobManager(lifecycle)
    jobs = [manager.cleanup(record.sandbox_id, force=False) for _ in range(2)]
    for _ in range(200):
        statuses = [manager.get(job["job_id"])["status"] for job in jobs]
        if all(status in {"REMOVED", "FAILED"} for status in statuses):
            break
        time.sleep(0.01)
    statuses = [manager.get(job["job_id"])["status"] for job in jobs]
    assert statuses.count("REMOVED") == 1
    assert statuses.count("FAILED") == 1
