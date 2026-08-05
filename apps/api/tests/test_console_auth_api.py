from __future__ import annotations

from testing.app_factory import create_test_app
from fastapi.testclient import TestClient


def _local_client(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    app = create_test_app()
    return app, TestClient(app)


def test_local_auth_requires_login_and_reports_session(monkeypatch):
    app, client = _local_client(monkeypatch)
    with client:
        assert client.get("/auth/session").json() == {"status": "anonymous"}
        response = client.get("/console/bootstrap")
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "unauthorized"


def test_initial_login_requires_password_change(monkeypatch):
    app, client = _local_client(monkeypatch)
    with client:
        admin = app.state.console_auth_service
        credentials = awaitable_result(admin.store.get_admin("admin"))
        assert credentials is not None
        # Tests use a controlled reset rather than relying on emitted logs.
        initial = awaitable_result(admin.rotate_initial_password())
        response = client.post("/auth/login", json={"username": "admin", "password": initial})
        assert response.status_code == 200
        assert response.json()["status"] == "password_change_required"
        assert "HttpOnly" in response.headers["set-cookie"]
        assert client.get("/console/bootstrap").status_code == 403


def test_change_password_unlocks_console_and_logout_revokes_cookie(monkeypatch):
    app, client = _local_client(monkeypatch)
    with client:
        initial = awaitable_result(app.state.console_auth_service.rotate_initial_password())
        assert client.post("/auth/login", json={"username": "admin", "password": initial}).status_code == 200
        changed = client.post(
            "/auth/change-password",
            json={"current_password": initial, "new_password": "Correct Horse Battery Staple 2026!"},
        )
        assert changed.status_code == 200
        assert changed.json()["status"] == "authenticated"
        assert client.get("/console/bootstrap").status_code == 200
        assert client.post("/auth/logout").status_code == 204
        assert client.get("/console/bootstrap").status_code == 401


def test_auth_rejects_cross_site_password_change(monkeypatch):
    app, client = _local_client(monkeypatch)
    with client:
        response = client.post(
            "/auth/change-password",
            headers={"Origin": "https://attacker.invalid"},
            json={"current_password": "x", "new_password": "Correct Horse Battery Staple 2026!"},
        )
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "cross_site_request"


def awaitable_result(awaitable):
    import asyncio

    return asyncio.run(awaitable)
