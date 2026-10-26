from fastapi.testclient import TestClient

from tier1.api import create_app


def test_root_accepts_render_head_health_probe(monkeypatch):
    monkeypatch.setenv("TIER1_PROVIDER", "mock")
    response = TestClient(create_app()).head("/")
    assert response.status_code == 200
