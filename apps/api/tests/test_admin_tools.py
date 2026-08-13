"""Admin tools API tests."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from jose import jwt


def test_tool_lookup_honors_explicit_domain() -> None:
    from routes.admin_tools import _find_tool

    class Registry:
        def keys(self):
            return ["alpha", "beta"]

        def get(self, route: str):
            return [SimpleNamespace(name="same_name", route=route)]

    found = _find_tool(Registry(), "same_name", route="beta")

    assert found is not None
    assert found[0] == "beta"


def test_admin_tools_returns_matrix(client) -> None:
    r = client.get("/admin/tools")
    assert r.status_code == 200
    body = r.json()
    assert "tools" in body and "matrix" in body
    assert "roles" in body["matrix"]
    names = {t["name"] for t in body["tools"]}
    assert "search_knowledge" in names or "echo" in names


def test_admin_tools_exposes_all_required_permissions(client) -> None:
    response = client.get("/admin/tools")

    assert response.status_code == 200
    draft_tool = next(
        tool
        for tool in response.json()["tools"]
        if tool["name"] == "prepare_work_order_draft"
    )
    assert draft_tool["required_permissions_all"] == [
        "workorder:create",
        "workorder:assign",
    ]


def test_permission_only_matrix_does_not_claim_role_denial(client) -> None:
    body = client.get("/admin/tools").json()
    draft_tool = next(
        tool for tool in body["tools"] if tool["name"] == "prepare_work_order_draft"
    )
    assert body["matrix"]["tools"][draft_tool["tool_id"]]["admin"] == "permission_required"


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
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
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
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
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
