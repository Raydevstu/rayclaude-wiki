from dataclasses import replace

from tier1.memory import MemoryAdapter
from tier1.store import Store


def test_local_memory_round_trip_survives_fresh_store_instance(tmp_path, settings):
    path = str(tmp_path / "continuity.db")
    first = MemoryAdapter(replace(settings, db_path=path), Store(path))
    added = first.add("Current project is Tier-1 Control Plane.", "project")
    assert added["status"] == "available"
    assert added["source"] == "sqlite"

    second = MemoryAdapter(replace(settings, db_path=path), Store(path))
    found = second.search("Tier-1 Control Plane")
    assert found["status"] == "available"
    assert "Tier-1 Control Plane" in found["results"][0]


def test_remote_memory_without_url_is_explicitly_unavailable(settings):
    adapter = MemoryAdapter(settings, Store(":memory:"))
    state = adapter.remote_status()
    assert state["status"] == "unavailable"
    assert state["source"] == "local"
    assert "TIER1_MEMORY_URL" in state["error"]


def test_remote_failure_is_not_silently_mixed_into_local_memory(settings, monkeypatch):
    remote_settings = replace(settings, memory_url="http://memory.invalid", memory_tenant_id="t",
                              memory_bank_id="b", memory_project_id="p")
    adapter = MemoryAdapter(remote_settings, Store(":memory:"))
    from tier1.memory_remote import RemoteMemoryError
    monkeypatch.setattr("tier1.memory.RemoteMemory.capture", lambda *_: (_ for _ in ()).throw(RemoteMemoryError("boom")))
    result = adapter.add("must not fall back")
    assert result["status"] == "failed"
    assert result["source"] == "remote"
