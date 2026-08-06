"""Admin domains RBAC."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from jose import jwt


def test_admin_domains_ok_with_star(client: TestClient) -> None:
    # auth off → permissions=["*"]
    r = client.get("/admin/domains")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "domains" in body
    names = {d["name"] for d in body["domains"]}
    assert "echo" in names


def test_admin_domains_returns_object_shape(client: TestClient) -> None:
    r = client.get("/admin/domains")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "domains" in body
    assert isinstance(body["domains"], list)
    if body["domains"]:
        entry = body["domains"][0]
        assert "name" in entry
        assert "description" in entry
        assert "tools" in entry
        assert "required_permissions" in entry
        assert "required_permissions_all" in entry
        assert "tool_details" in entry
        assert "approval_actions" in entry
        assert "graph_registered" in entry


def test_admin_domains_exposes_per_tool_rules_and_approval_actions(
    client: TestClient,
) -> None:
    body = client.get("/admin/domains").json()
    catalog = {item["name"]: item for item in body["domains"]}

    work_order = catalog["work_order_ops"]
    draft = next(
        item for item in work_order["tool_details"] if item["name"] == "prepare_work_order_draft"
    )
    assert draft["required_permissions_all"] == ["workorder:create", "workorder:assign"]
    assert work_order["approval_actions"] == [
        {
            "type": "work_order_ops.create_v1",
            "resource": {
                "name": "create_work_order",
                "required_permissions_all": ["workorder:create", "workorder:assign"],
            },
        }
    ]


def test_admin_domains_forbidden_without_perm(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "admin-rbac-secret"
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
            "sub": "u1",
            "tenant_id": "acme",
            "roles": ["viewer"],
            "permissions": [],
        },
        secret,
        algorithm="HS256",
    )
    with TestClient(app) as c:
        r = c.get(
            "/admin/domains",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "forbidden"
