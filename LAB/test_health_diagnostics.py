from fastapi.testclient import TestClient

from tier1.api import create_app


def test_health_reports_ephemeral_sqlite_storage():
    response = TestClient(create_app()).get("/health")
    body = response.json()
    assert body["status"] == "ok"
    assert body["persistence"] == "sqlite"
    assert body["durable"] is False
    assert "ephemeral" in body["warning"]
