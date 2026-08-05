from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from testing.app_factory import create_test_app


def test_local_authenticated_request_refreshes_session_idle_window(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    app = create_test_app()
    with TestClient(app) as client:
        service = app.state.console_auth_service
        initial = asyncio.run(service.rotate_initial_password())
        assert client.post("/auth/login", json={"username": "admin", "password": initial}).status_code == 200
        assert client.post(
            "/auth/change-password",
            json={"current_password": initial, "new_password": "Correct Horse Battery Staple 2026!"},
        ).status_code == 200
        token = client.cookies.get(app.state.settings.auth_cookie_name)
        assert token
        before = asyncio.run(service.store.get_session(service.hash_session(token)))
        assert before is not None
        assert client.get("/console/bootstrap").status_code == 200
        after = asyncio.run(service.store.get_session(service.hash_session(token)))
        assert after is not None
        assert after["last_seen_at"] >= before["last_seen_at"]
