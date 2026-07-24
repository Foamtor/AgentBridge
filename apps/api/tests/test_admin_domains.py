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
    names = {d["name"] for d in r.json()}
    assert "echo" in names


def test_admin_domains_forbidden_without_perm(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "admin-rbac-secret"
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_DEV_STUB", "false")
    monkeypatch.setenv("OIDC_JWT_SECRET", secret)
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "1")
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["AUTH_DEV_STUB"] = "false"
    os.environ["OIDC_JWT_SECRET"] = secret
    from main import create_app

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
