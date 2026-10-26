from pathlib import Path

import yaml


def test_render_blueprint_wires_durable_database_without_literal_secret():
    document = yaml.safe_load(Path("render.yaml").read_text(encoding="utf-8"))
    service = document["services"][0]
    database = document["databases"][0]
    env = {entry["key"]: entry for entry in service["envVars"]}
    assert service["runtime"] == "docker"
    assert env["TIER1_DATABASE_URL"]["fromDatabase"]["name"] == database["name"]
    assert env["TIER1_DATABASE_URL"]["fromDatabase"]["property"] == "connectionString"
    assert env["TIER1_API_TOKEN"]["generateValue"] is True
    assert "password" not in Path("render.yaml").read_text(encoding="utf-8").lower()
