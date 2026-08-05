from __future__ import annotations

from fastapi.testclient import TestClient

from testing.app_factory import create_test_app


def test_bootstrap_requires_local_session_and_returns_safe_snapshot(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    app = create_test_app()
    with TestClient(app) as client:
        initial = client.get("/console/bootstrap")
        assert initial.status_code == 401
        password = __import__("asyncio").run(app.state.console_auth_service.rotate_initial_password())
        assert client.post("/auth/login", json={"username": "admin", "password": password}).json()["status"] == "password_change_required"
        assert client.post("/auth/change-password", json={"current_password": password, "new_password": "Correct Horse Battery Staple 2026!"}).status_code == 200
        response = client.get("/console/bootstrap")
        assert response.status_code == 200
        body = response.json()
        assert body["runtime"]["auth_mode"] == "local"
        assert body["reference"]["route"] == "work_order_ops"
        assert "password" not in response.text.lower()
        assert "dsn" not in response.text.lower()
