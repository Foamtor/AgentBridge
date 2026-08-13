from __future__ import annotations

from agentbridge_core.adapters.fake_data_source import FakeDataSource
from fastapi.testclient import TestClient
from testing.app_factory import create_test_app


def test_bootstrap_requires_local_session_and_returns_safe_snapshot(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    monkeypatch.setenv("ENABLE_DATA_SOURCE", "false")
    monkeypatch.setenv("USE_MEMORY_CHECKPOINTER", "true")
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
        assert body["runtime"]["observability_backend"] == "memory"
        assert body["runtime"]["checkpointer_backend"] == "memory"
        assert body["reference"]["route"] == "work_order_ops"
        assert "password" not in response.text.lower()
        assert "dsn" not in response.text.lower()


def test_bootstrap_marks_the_postgres_fallback_as_a_configured_source(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    monkeypatch.setenv("ENABLE_DATA_SOURCE", "true")
    monkeypatch.setenv("USE_MEMORY_CHECKPOINTER", "true")
    app = create_test_app()
    app.state.bootstrap_data_source = FakeDataSource()
    with TestClient(app) as client:
        password = __import__("asyncio").run(app.state.console_auth_service.rotate_initial_password())
        client.post("/auth/login", json={"username": "admin", "password": password})
        client.post(
            "/auth/change-password",
            json={"current_password": password, "new_password": "Correct Horse Battery Staple 2026!"},
        )

        assert client.get("/console/bootstrap").json()["reference"]["data_class"] == "configured_source"
