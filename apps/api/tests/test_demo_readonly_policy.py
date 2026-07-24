"""demo_readonly policy + FakeDataSource tenant filter tests."""

from __future__ import annotations

import pytest
from agent_base_core.adapters.fake_data_source import FakeDataSource
from agent_base_core.adapters.role_policy import RolePolicyEngine
from agent_base_core.protocol.context import RUN_CONTEXT_KEY, RunContext, get_run_context
from agent_base_core.protocol.tool_meta import get_tool_meta
from fastapi.testclient import TestClient
from jose import jwt

from domains.demo_readonly.tools import list_orders


def test_list_orders_requires_order_read_permission() -> None:
    meta = get_tool_meta(list_orders)
    assert meta["required_permissions"] == ["order:read"]
    engine = RolePolicyEngine()
    viewer = RunContext(roles=["viewer"], permissions=[])
    admin_reader = RunContext(roles=["viewer"], permissions=["order:read"])
    filtered_viewer = engine.filter_tools("demo_readonly", [list_orders], viewer)
    filtered_reader = engine.filter_tools("demo_readonly", [list_orders], admin_reader)
    assert filtered_viewer == []
    assert filtered_reader == [list_orders]
    assert (
        engine.decide(
            ctx=viewer,
            action="invoke_tool",
            resource={
                "name": "list_orders",
                "required_roles": [],
                "required_permissions": ["order:read"],
            },
        )
        == "deny"
    )


@pytest.mark.asyncio
async def test_list_orders_uses_tenant_and_data_source() -> None:
    ds = FakeDataSource()
    ds.seed(
        "demo_orders",
        [
            {"id": 1, "tenant_id": "acme", "status": "open"},
            {"id": 2, "tenant_id": "other", "status": "open"},
        ],
    )
    ctx = RunContext(
        tenant_id="acme",
        user_id="u1",
        permissions=["order:read"],
        metadata={"data_source": ds},
    )
    config = {"configurable": {RUN_CONTEXT_KEY: ctx}}
    rows = await list_orders.ainvoke({"status": "open"}, config=config)
    assert rows == [{"id": 1, "tenant_id": "acme", "status": "open"}]
    assert ds.last_params == ("open", "acme")
    assert get_run_context(config).metadata["data_source"] is ds


def test_chat_injects_data_source_into_run_context(client: TestClient) -> None:
    from agent_base_core.adapters.fake_data_source import FakeDataSource

    fake = FakeDataSource()
    client.app.state.data_source = fake
    # Auth off → claims_to_run_context gives admin + *; stream should succeed
    # and pipeline/lifecycle receives ctx with metadata data_source.
    # Capture via a tiny hook on pipeline.handle.
    seen: dict = {}
    orig = client.app.state.pipeline.handle

    async def _capture(**kwargs):
        seen["ctx"] = kwargs.get("ctx")
        return await orig(**kwargs)

    client.app.state.pipeline.handle = _capture  # type: ignore[method-assign]
    r = client.post(
        "/chat/stream",
        json={"query": "hi", "thread_id": "t-ds-meta", "route": "echo"},
    )
    assert r.status_code == 200
    assert seen["ctx"] is not None
    assert seen["ctx"].metadata.get("data_source") is fake


def test_viewer_jwt_hides_list_orders_from_tool_list(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "plan2-matrix-secret"
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_DEV_STUB", "false")
    monkeypatch.setenv("OIDC_JWT_SECRET", secret)
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "1")
    import os

    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["AUTH_DEV_STUB"] = "false"
    os.environ["OIDC_JWT_SECRET"] = secret
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    token = jwt.encode(
        {
            "sub": "v1",
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
                "query": "orders",
                "thread_id": "t-readonly-viewer",
                "route": "demo_readonly",
            },
        )
        assert r.status_code == 200
        # list_tools audit: after filter should be 0 tools for viewer
        audits = [
            a
            for a in c.app.state.audit.records
            if a["action"] == "list_tools" and a["resource"] == "demo_readonly"
        ]
        assert audits
        assert audits[-1]["detail"]["after"] == 0
