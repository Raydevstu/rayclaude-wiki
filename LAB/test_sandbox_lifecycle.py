import json

import pytest

from tier1.sandbox_lifecycle import SandboxLifecycle


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
