import pytest
import json

from tier1.sandbox_adapter import resolve_write_root


def test_write_root_requires_explicit_provisioning(tmp_path, monkeypatch):
    monkeypatch.delenv("TIER1_GUARD_SANDBOX_ROOT", raising=False)
    with pytest.raises(RuntimeError, match="not configured"):
        resolve_write_root()


def test_write_root_requires_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("TIER1_GUARD_SANDBOX_ROOT", str(tmp_path))
    with pytest.raises(RuntimeError, match="not provisioned"):
        resolve_write_root()


def test_write_root_accepts_provisioned_sandbox(tmp_path, monkeypatch):
    (tmp_path / ".tier1-sandbox").write_text("tier1-sandbox-v1\n", encoding="utf-8")
    monkeypatch.setenv("TIER1_GUARD_SANDBOX_ROOT", str(tmp_path))
    assert resolve_write_root() == tmp_path.resolve()


def test_write_root_rejects_expired_managed_sandbox(tmp_path, monkeypatch):
    (tmp_path / ".tier1-sandbox").write_text("tier1-sandbox-v1\n", encoding="utf-8")
    (tmp_path / ".tier1-sandbox.json").write_text(json.dumps({
        "version": "tier1-sandbox-v1", "expires_at": 0,
    }), encoding="utf-8")
    monkeypatch.setenv("TIER1_GUARD_SANDBOX_ROOT", str(tmp_path))
    with pytest.raises(RuntimeError, match="expired"):
        resolve_write_root()
