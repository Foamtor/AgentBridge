"""Admin tools API tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from jose import jwt


def test_admin_tools_returns_matrix(client) -> None:
    r = client.get("/admin/tools")
    assert r.status_code == 200
    body = r.json()
    assert "tools" in body and "matrix" in body
    assert "roles" in body["matrix"]
    names = {t["name"] for t in body["tools"]}
    assert "search_knowledge" in names or "echo" in names


def test_tool_invoke_disabled_by_default(client) -> None:
    r = client.post(
        "/admin/tools/search_knowledge/invoke",
        json={"arguments": {"query": "x"}},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "tool_invoke_disabled"


def test_tool_invoke_when_enabled(monkeypatch: pytest.MonkeyPatch, client) -> None:
    monkeypatch.setenv("ADMIN_TOOL_INVOKE_ENABLED", "true")
    os.environ["ADMIN_TOOL_INVOKE_ENABLED"] = "true"
    from testing.app_factory import create_test_app as create_app

    with TestClient(create_app()) as c:
        r = c.post(
            "/admin/tools/add/invoke",
            json={"arguments": {"a": 1, "b": 2}},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["result"] == 3


def test_admin_tools_ok_with_admin_read(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "tools-read-secret"
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_DEV_STUB", "false")
    monkeypatch.setenv("OIDC_JWT_SECRET", secret)
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "1")
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["AUTH_DEV_STUB"] = "false"
    os.environ["OIDC_JWT_SECRET"] = secret
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    token = jwt.encode(
        {
            "sub": "u-read",
            "tenant_id": "default",
            "roles": ["viewer"],
            "permissions": ["admin:read"],
        },
        secret,
        algorithm="HS256",
    )
    with TestClient(app) as c:
        r = c.get("/admin/tools", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert "tools" in r.json()


def test_tool_invoke_denied_by_policy_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "tools-invoke-deny-secret"
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_DEV_STUB", "false")
    monkeypatch.setenv("OIDC_JWT_SECRET", secret)
    monkeypatch.setenv("ADMIN_TOOL_INVOKE_ENABLED", "true")
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "1")
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["AUTH_DEV_STUB"] = "false"
    os.environ["OIDC_JWT_SECRET"] = secret
    os.environ["ADMIN_TOOL_INVOKE_ENABLED"] = "true"
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    token = jwt.encode(
        {
            "sub": "u-viewer",
            "tenant_id": "default",
            "roles": ["viewer"],
            "permissions": ["admin:tools"],
        },
        secret,
        algorithm="HS256",
    )
    with TestClient(app) as c:
        r = c.post(
            "/admin/tools/delete_records/invoke",
            json={"arguments": {"table": "orders"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "forbidden"
