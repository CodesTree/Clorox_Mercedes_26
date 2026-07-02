from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok_and_version():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_cors_allows_the_dev_frontend_origin():
    with TestClient(app) as client:
        resp = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
