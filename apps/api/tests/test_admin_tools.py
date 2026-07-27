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
