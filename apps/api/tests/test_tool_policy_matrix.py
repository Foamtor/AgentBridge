"""M2a gate: viewer/admin tool matrix + list audit + invoke deny."""

from __future__ import annotations

import os

import pytest
from agent_base_core.adapters.memory_audit_logger import MemoryAuditLogger
from agent_base_core.adapters.role_policy import RolePolicyEngine
from agent_base_core.application.pipeline import PipelineRequest, ToolPolicyPlugin
from agent_base_core.application.tool_guard import guard_tools
from agent_base_core.protocol.context import RunContext
from fastapi.testclient import TestClient
from jose import jwt

from domains.demo_tools.tools import add, delete_records


def _tool_names(tools: list) -> set[str]:
    return {getattr(t, "name", "") for t in tools}


@pytest.mark.asyncio
async def test_viewer_list_filters_delete_admin_keeps_both() -> None:
    policy = RolePolicyEngine()
    audit = MemoryAuditLogger()

    class _Reg:
        def get(self, route: str):
            return [add, delete_records]

    plugin = ToolPolicyPlugin(policy=policy, audit=audit, tools_registry=_Reg())  # type: ignore[arg-type]
    viewer_req = PipelineRequest(
        query="q",
        thread_id="t",
        route="demo_tools",
        sink=None,  # type: ignore[arg-type]
        ctx=RunContext(user_id="v", tenant_id="t", roles=["viewer"]),
    )
    viewer_out = await plugin.before_run(viewer_req)
    assert _tool_names(viewer_out.tools_override or []) == {"add"}
    assert any(r["action"] == "list_tools" for r in audit.records)

    admin_req = PipelineRequest(
        query="q",
        thread_id="t",
        route="demo_tools",
        sink=None,  # type: ignore[arg-type]
        ctx=RunContext(user_id="a", tenant_id="t", roles=["admin"]),
    )
    admin_out = await plugin.before_run(admin_req)
    assert _tool_names(admin_out.tools_override or []) == {"add", "delete_records"}


@pytest.mark.asyncio
async def test_invoke_deny_for_viewer_on_delete_records() -> None:
    policy = RolePolicyEngine()
    audit = MemoryAuditLogger()
    ctx = RunContext(user_id="v", tenant_id="t", roles=["viewer"])
    guarded = guard_tools([delete_records], policy=policy, ctx=ctx, audit=audit)
    result = await guarded[0].ainvoke({"table": "users"})
    assert result == "forbidden"
    assert any(r["result"] == "denied" for r in audit.records)


def test_chat_stream_with_viewer_jwt_audits_list_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "matrix-test-secret"
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
            "sub": "viewer-1",
            "tenant_id": "acme",
            "roles": ["viewer"],
            "permissions": [],
        },
        secret,
        algorithm="HS256",
    )
    with TestClient(app) as c:
        r = c.post(
            "/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "query": "hi",
                "thread_id": "t-matrix-viewer",
                "route": "demo_tools",
            },
        )
        assert r.status_code == 200
        audit = c.app.state.audit
        assert any(
            rec["action"] == "list_tools" and rec["user_id"] == "viewer-1"
            for rec in audit.records
        )
