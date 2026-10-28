from fastapi.testclient import TestClient

from backend.app import app


def test_health() -> None:
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["model"]
