"""Health endpoint tests."""

from fastapi.testclient import TestClient

from testing.app_factory import create_test_app as create_app


def test_health():
    with TestClient(create_app()) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
