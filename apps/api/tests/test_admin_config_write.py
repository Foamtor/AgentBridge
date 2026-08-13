"""Admin config write API tests."""

from __future__ import annotations


def test_put_config_rejects_tier_b_and_c(client) -> None:
    r = client.put("/admin/config/LLM_BACKEND", json={"value": "gateway"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "config_not_writable"


def test_put_config_tier_a_updates_value(client) -> None:
    r = client.put("/admin/config/RATE_LIMIT_PER_MINUTE", json={"value": 42})
    assert r.status_code == 200
    body = r.json()
    assert body["key"] == "RATE_LIMIT_PER_MINUTE"
    assert body["value"] == 42
    assert body["tier"] == "A"
    assert body["source"] == "memory"
    cfg = client.get("/admin/config")
    item = next(x for x in cfg.json()["items"] if x["key"] == "RATE_LIMIT_PER_MINUTE")
    assert item["value"] == 42
    assert item["source"] == "memory"
    assert client.app.state.settings.rate_limit_per_minute == 42


def test_put_config_validates_runtime_value(client) -> None:
    response = client.put("/admin/config/RATE_LIMIT_PER_MINUTE", json={"value": True})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_config_value"

    response = client.put("/admin/config/ADMIN_TOOL_INVOKE_ENABLED", json={"value": "true"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_config_value"


def test_put_config_updates_boolean_runtime_value(client) -> None:
    response = client.put("/admin/config/ADMIN_TOOL_INVOKE_ENABLED", json={"value": True})
    assert response.status_code == 200
    assert client.app.state.settings.admin_tool_invoke_enabled is True


def test_local_config_write_requires_current_password(monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from testing.app_factory import create_test_app

    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    app = create_test_app()
    with TestClient(app) as client:
        service = app.state.console_auth_service
        initial = __import__("asyncio").run(service.rotate_initial_password())
        assert client.post("/auth/login", json={"username": "admin", "password": initial}).status_code == 200
        new_password = "Password2026"
        assert client.post("/auth/change-password", json={"current_password": initial, "new_password": new_password}).status_code == 200

        missing = client.put("/admin/config/RATE_LIMIT_PER_MINUTE", json={"value": 42})
        assert missing.status_code == 401
        assert missing.json()["detail"]["code"] == "current_password_required"

        wrong = client.put("/admin/config/RATE_LIMIT_PER_MINUTE", json={"value": 42, "current_password": "wrong"})
        assert wrong.status_code == 401
        assert wrong.json()["detail"]["code"] == "reauth_invalid_credentials"

        accepted = client.put("/admin/config/RATE_LIMIT_PER_MINUTE", json={"value": 42, "current_password": new_password})
        assert accepted.status_code == 200
        assert accepted.json()["source"] == "memory"
