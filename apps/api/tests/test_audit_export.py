"""Admin audit export."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient


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
