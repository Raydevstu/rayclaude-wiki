from fastapi.testclient import TestClient

from tier1.api import create_app


def test_docs_catalog_contains_categories_and_faq():
    body = TestClient(create_app()).get("/v1/docs").json()
    assert "faq" in body
    assert any(item["path"] == "README.md" for item in body["documents"])
    assert {item["category"] for item in body["documents"]} >= {"Getting Started", "Reference"}


def test_docs_content_is_readable_and_path_traversal_is_blocked():
    client = TestClient(create_app())
    listing = client.get("/v1/docs").json()
    readme = next(item for item in listing["documents"] if item["path"] == "README.md")
    response = client.get("/v1/docs/" + readme["id"])
    assert response.status_code == 200
    assert response.json()["path"] == "README.md"
    assert "Tier-1" in response.json()["content"]
    assert client.get("/v1/docs/..%2F..%2Fsecrets.txt").status_code == 404
