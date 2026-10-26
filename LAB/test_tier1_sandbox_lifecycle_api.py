from fastapi.testclient import TestClient

from tier1.api import create_app


def test_sandbox_lifecycle_api_provisions_and_requires_force_for_early_cleanup(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.txt").write_text("before", encoding="utf-8")
    monkeypatch.setenv("TIER1_SANDBOX_PARENT", str(tmp_path / "sandboxes"))
    monkeypatch.setenv("TIER1_GUARD_ROOT", str(source))
    client = TestClient(create_app())
    created = client.post("/v1/guard/sandboxes", json={"ttl_seconds": 60})
    assert created.status_code == 200
    sandbox_id = created.json()["sandbox_id"]
    listed = client.get("/v1/guard/sandboxes")
    assert listed.status_code == 200
    item = next(x for x in listed.json()["sandboxes"] if x["sandbox_id"] == sandbox_id)
    assert item["status"] == "READY"
    assert item["repository"]["branch"] == "main"
    detail = client.get(f"/v1/guard/sandboxes/{sandbox_id}")
    assert detail.status_code == 200
    assert detail.json()["root"].endswith(sandbox_id)
    early = client.delete(f"/v1/guard/sandboxes/{sandbox_id}")
    assert early.status_code == 409
    removed = client.delete(f"/v1/guard/sandboxes/{sandbox_id}?force=true")
    assert removed.status_code == 200
    assert removed.json()["status"] == "REMOVED"
