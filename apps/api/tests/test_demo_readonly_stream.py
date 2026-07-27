"""demo_readonly end-to-end stream with policy + FakeDataSource."""

from __future__ import annotations

import json

import pytest
from agentbridge_core.adapters.fake_data_source import FakeDataSource
from fastapi.testclient import TestClient


def _parse_sse(body: str) -> list[dict]:
    events: list[dict] = []
    for block in body.split("\n\n"):
        line = block.strip()
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[len("data: ") :]))
    return events


def test_demo_readonly_stream_queries_with_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real LangGraph + RolePolicy + InjectedToolArg must still reach DataSource."""
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "0")
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    fake = FakeDataSource()
    # auth-off RunContext uses tenant_id=dev
    fake.seed(
        "demo_orders",
        [
            {"id": 1, "tenant_id": "dev", "status": "open"},
            {"id": 2, "tenant_id": "other", "status": "open"},
        ],
    )
    with TestClient(app) as c:
        c.app.state.data_source = fake
        r = c.post(
            "/chat/stream",
            json={
                "query": "list open orders",
                "thread_id": "t-demo-readonly-e2e",
                "route": "demo_readonly",
            },
        )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert "tool_call" in types
    assert "tool_result" in types
    assert "x.demo_readonly.finished" in types
    assert types[-1] == "done"
    result = next(e for e in events if e["type"] == "tool_result")
    assert result["data"]["ok"] is True
    assert fake.last_params == ("open", "dev")
    assert "1" in result["data"]["summary"]
    assert "other" not in result["data"]["summary"]
