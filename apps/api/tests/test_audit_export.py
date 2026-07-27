"""Admin audit export."""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient
from jose import jwt


def test_audit_export_jsonl_redacts_query(client: TestClient) -> None:
    audit = client.app.state.audit
    audit.records.append(
        {
            "user_id": "u1",
            "tenant_id": "acme",
            "action": "list_tools",
            "resource": "demo_tools",
            "result": "allow",
            "detail": {
                "policy_version": "role_policy/v1",
                "query": "secret user text",
                "reason_code": "ok",
            },
        }
    )
    r = client.get("/admin/audit/export")
    assert r.status_code == 200
    assert "application/x-ndjson" in r.headers.get("content-type", "")
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    assert lines
    row = json.loads(lines[-1])
    assert row["action"] == "list_tools"
    assert row["detail"].get("policy_version") == "role_policy/v1"
    assert "query" not in row["detail"]


def test_audit_export_forbidden_without_perm(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "audit-export-secret"
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
            "/admin/audit/export",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "forbidden"


def test_policy_bundle_version_flows_to_audit_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "policy-ver-secret"
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_DEV_STUB", "false")
    monkeypatch.setenv("OIDC_JWT_SECRET", secret)
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    monkeypatch.setenv("POLICY_BUNDLE_VERSION", "bundle/e2e-v3")
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["AUTH_DEV_STUB"] = "false"
    os.environ["OIDC_JWT_SECRET"] = secret
    os.environ["POLICY_BUNDLE_VERSION"] = "bundle/e2e-v3"
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    token = jwt.encode(
        {
            "sub": "viewer-1",
            "tenant_id": "acme",
            "roles": ["viewer"],
            "permissions": ["admin:audit"],
        },
        secret,
        algorithm="HS256",
    )
    with TestClient(app) as c:
        stream = c.post(
            "/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "query": "hi",
                "thread_id": "t-policy-ver",
                "route": "demo_tools",
            },
        )
        assert stream.status_code == 200
        export = c.get(
            "/admin/audit/export",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert export.status_code == 200
        rows = [
            json.loads(ln)
            for ln in export.text.splitlines()
            if ln.strip()
        ]
        list_rows = [r for r in rows if r.get("action") == "list_tools"]
        assert list_rows
        assert list_rows[-1]["detail"].get("policy_version") == "bundle/e2e-v3"
