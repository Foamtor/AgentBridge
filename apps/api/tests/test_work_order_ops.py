"""Golden-case work-order operations API contract."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from agentbridge_core.adapters.fake_data_source import FakeDataSource
from agentbridge_core.adapters.fake_retriever import FakeRetriever
from agentbridge_core.protocol.context import RunContext
from domains.work_order_ops.approval import make_create_work_order_handler
from domains.work_order_ops.graph import _chart_payload
from fastapi.testclient import TestClient


def _events(body: str) -> list[dict]:
    return [
        json.loads(block.strip()[6:])
        for block in body.split("\n\n")
        if block.strip().startswith("data: ")
    ]


def test_work_order_ops_emits_structured_business_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "0")
    from testing.app_factory import create_test_app

    app = create_test_app()
    source = FakeDataSource()
    source.seed(
        "work_orders",
        [
            {"id": "WO-DEMO-1", "tenant_id": "dev", "title": "脱敏网络告警", "status": "open", "priority": "high", "assignee_id": "assignee-demo-a"},
            {"id": "WO-OTHER-1", "tenant_id": "other", "title": "other", "status": "closed", "priority": "low", "assignee_id": "assignee-demo-b"},
        ],
    )
    app.state.bootstrap_data_source = source
    retriever = FakeRetriever()
    import asyncio
    asyncio.run(retriever.ingest([{"chunk_id": "wo-sop-1", "doc_id": "wo-sop", "text": "show work orders SOP"}], tenant_id="dev"))
    with TestClient(app) as client:
        client.app.state.retriever = retriever
        response = client.post(
            "/chat/stream",
            json={"query": "show work orders", "thread_id": "wo-1", "route": "work_order_ops"},
        )

    assert response.status_code == 200
    types = [event["type"] for event in _events(response.text)]
    assert "x.work_order_ops.list" in types
    assert "x.work_order_ops.chart" in types
    assert "x.bridge.citation" in types
    citation = next(event for event in _events(response.text) if event["type"] == "x.bridge.citation")
    assert citation["data"]["citations"][0]["chunk_id"] == "wo-sop-1"
    listing = next(event for event in _events(response.text) if event["type"] == "x.work_order_ops.list")
    assert listing["data"]["rows"] == [{"id": "WO-DEMO-1", "title": "脱敏网络告警", "status": "open", "priority": "high", "assignee_id": "assignee-demo-a"}]
    chart = next(event for event in _events(response.text) if event["type"] == "x.work_order_ops.chart")
    option = chart["data"]["echarts_option"]
    assert option["xAxis"]["type"] == "category"
    assert option["series"][0]["type"] == "bar"


def test_work_order_ops_create_emits_draft_and_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "0")
    from testing.app_factory import create_test_app

    app = create_test_app()
    source = FakeDataSource()
    source.seed("assignees", [{"id": "assignee-demo-a", "tenant_id": "dev", "active": True}])
    app.state.bootstrap_data_source = source
    with TestClient(app) as client:
        response = client.post("/chat/stream", json={"query": "create work order", "thread_id": "wo-create", "route": "work_order_ops"})
        events = _events(response.text)
        preview = next(event for event in events if event["type"] == "x.work_order_ops.ledger_preview")
        required = next(event for event in events if event["type"] == "x.bridge.approval_required")
        assert preview["data"]["approval_required"] is True
        assert required["data"]["action"]["type"] == "work_order_ops.create_v1"
        assert awaitable_empty(source, "work_orders")
        approval_id = required["data"]["approval_id"]
        approved = client.post(f"/approvals/{approval_id}", json={"decision": "approve"})
        repeated = client.post(f"/approvals/{approval_id}", json={"decision": "approve"})
    assert approved.status_code == 200
    assert repeated.status_code == 200
    assert len(source._tables["work_orders"]) == 1
    assert len(source._tables["ledgers"]) == 1


def awaitable_empty(source: FakeDataSource, table: str) -> bool:
    return source._tables.get(table, []) == []


@pytest.mark.parametrize("query, expected", [("bar", "bar"), ("line trend", "line"), ("pie chart", "pie")])
def test_chart_payload_supports_echarts_types(query: str, expected: str) -> None:
    payload = _chart_payload([{"status": "open"}, {"status": "closed"}], query)
    assert payload["chart_type"] == expected
    assert payload["echarts_option"]["series"][0]["type"] == expected


@pytest.mark.asyncio
async def test_create_handler_is_transactional_and_idempotent() -> None:
    source = FakeDataSource()
    source.seed(
        "assignees",
        [{"id": "a1", "tenant_id": "acme", "active": True}],
    )
    handler = make_create_work_order_handler(source)
    action = {
        "type": "work_order_ops.create_v1",
        "payload": {
            "draft_id": "d1",
            "title": "Synthetic alert",
            "priority": "high",
            "assignee_id": "a1",
            "ledger_summary": "Synthetic ledger",
        },
    }
    ctx = RunContext(tenant_id="acme")
    first = await handler(action=action, requester_ctx=ctx, approval_id="ap-1")
    second = await handler(action=action, requester_ctx=ctx, approval_id="ap-1")

    assert first == second
    assert len(await source.query(
        "SELECT * FROM work_orders WHERE tenant_id = $1", "acme"
    )) == 1
    assert len(await source.query(
        "SELECT * FROM ledgers WHERE tenant_id = $1", "acme"
    )) == 1


@pytest.mark.asyncio
async def test_create_handler_rejects_inactive_assignee_without_partial_write() -> None:
    source = FakeDataSource()
    source.seed(
        "assignees",
        [{"id": "a1", "tenant_id": "acme", "active": False}],
    )
    handler = make_create_work_order_handler(source)
    action = {
        "type": "work_order_ops.create_v1",
        "payload": {
            "draft_id": "d1",
            "title": "Synthetic alert",
            "priority": "high",
            "assignee_id": "a1",
            "ledger_summary": "Synthetic ledger",
        },
    }
    with pytest.raises(ValueError, match="assignee"):
        await handler(
            action=action,
            requester_ctx=RunContext(tenant_id="acme"),
            approval_id="ap-2",
        )
    assert await source.query(
        "SELECT * FROM work_orders WHERE tenant_id = $1", "acme"
    ) == []
    assert await source.query(
        "SELECT * FROM ledgers WHERE tenant_id = $1", "acme"
    ) == []


def test_work_order_ops_retriever_failure_is_not_an_empty_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingRetriever:
        async def similarity_search(self, query: str, *, tenant_id: str, k: int):
            raise RuntimeError("知识暂不可用")

        async def close(self) -> None:
            return None

    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "0")
    from testing.app_factory import create_test_app

    app = create_test_app()
    with TestClient(app) as client:
        client.app.state.retriever = FailingRetriever()
        response = client.post(
            "/chat/stream",
            json={
                "query": "show work orders",
                "thread_id": "wo-rag-failure",
                "route": "work_order_ops",
            },
        )
    events = _events(response.text)
    assert any(
        event["type"] == "error"
        and "知识暂不可用" in event["data"]["message"]
        for event in events
    )
    assert not any(event["type"] == "x.bridge.citation" for event in events)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("AGENTBRIDGE_TEST_PG_DSN"),
    reason="AGENTBRIDGE_TEST_PG_DSN not set",
)
async def test_postgres_handler_rebuilds_same_result_after_new_instance() -> None:
    import asyncpg
    from adapters.postgres_data_source import PostgresDataSource

    dsn = os.environ["AGENTBRIDGE_TEST_PG_DSN"]
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "005_work_order_ops.sql"
    )
    connection = await asyncpg.connect(dsn)
    try:
        await connection.execute(migration.read_text(encoding="utf-8"))
    finally:
        await connection.close()

    action = {
        "type": "work_order_ops.create_v1",
        "payload": {
            "draft_id": "pg-recovery",
            "title": "Synthetic recovery alert",
            "priority": "high",
            "assignee_id": "assignee-demo-a",
            "ledger_summary": "Synthetic recovery ledger",
        },
    }
    ctx = RunContext(tenant_id="acme")
    first_source = PostgresDataSource(dsn)
    try:
        first = await make_create_work_order_handler(first_source)(
            action=action, requester_ctx=ctx, approval_id="pg-recovery-test"
        )
    finally:
        await first_source.close()

    second_source = PostgresDataSource(dsn)
    try:
        second = await make_create_work_order_handler(second_source)(
            action=action, requester_ctx=ctx, approval_id="pg-recovery-test"
        )
    finally:
        await second_source.close()
    assert first == second
