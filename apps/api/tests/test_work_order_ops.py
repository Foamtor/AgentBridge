"""Golden-case work-order operations API contract."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from agentbridge_core.adapters.fake_data_source import FakeDataSource
from agentbridge_core.adapters.fake_retriever import FakeRetriever
from agentbridge_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agentbridge_core.adapters.inprocess_lock import InProcessThreadLock
from agentbridge_core.adapters.memory_audit_logger import MemoryAuditLogger
from agentbridge_core.adapters.memory_checkpointer import MemoryCheckpointerFactory
from agentbridge_core.adapters.memory_event_log import MemoryEventLog
from agentbridge_core.adapters.memory_message_store import MemoryMessageStore
from agentbridge_core.adapters.memory_run_store import MemoryRunStore
from agentbridge_core.adapters.noop_hooks import NoopHooks
from agentbridge_core.adapters.role_policy import RolePolicyEngine
from agentbridge_core.application.run_lifecycle import RunLifecycle
from agentbridge_core.application.tool_guard import guard_tools
from agentbridge_core.protocol.context import RUN_CONTEXT_KEY, RunContext
from agentbridge_core.registry.graphs import GraphRegistry
from agentbridge_core.registry.input_builders import InputBuilderRegistry
from agentbridge_core.registry.tools import ToolRegistry
from domains.work_order_ops.approval import make_create_work_order_handler
from domains.work_order_ops.graph import _chart_payload
from domains.work_order_ops.tools import prepare_work_order_draft
from fastapi.testclient import TestClient
from jose import jwt
from langchain_core.messages import AIMessage

ALL_WORK_ORDER_PERMISSIONS = [
    "workorder:read",
    "knowledge:read",
    "workorder:create",
    "workorder:assign",
    "approval:decide",
]
MISSING_FIELDS_MESSAGE = (
    "创建工单需要提供完整字段：title、priority、assignee_id、ledger_summary。"
)
DRAFT_VALIDATION_MESSAGE = (
    "工单草稿校验失败，请检查 title、priority、assignee_id 和 ledger_summary。"
)


def _events(body: str) -> list[dict]:
    return [
        json.loads(block.strip()[6:])
        for block in body.split("\n\n")
        if block.strip().startswith("data: ")
    ]


def _token(
    secret: str, *, permissions: list[str], tenant_id: str = "rag-agent-demo"
) -> str:
    return jwt.encode(
        {
            "sub": "work-order-user",
            "tenant_id": tenant_id,
            "roles": ["viewer"],
            "permissions": permissions,
        },
        secret,
        algorithm="HS256",
    )


def _configure_real_runtime_auth(
    monkeypatch: pytest.MonkeyPatch,
    *,
    secret: str,
) -> None:
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "0")
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_DEV_STUB", "false")
    monkeypatch.setenv("OIDC_JWT_SECRET", secret)


def _event_types(response_text: str) -> list[str]:
    return [event["type"] for event in _events(response_text)]


def _tool_call_names(response_text: str) -> list[str]:
    return [
        str(event["data"]["name"])
        for event in _events(response_text)
        if event["type"] == "tool_call"
    ]


class DraftGateway:
    def __init__(self, response: AIMessage) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def chat(
        self,
        messages: list[Any],
        *,
        ctx: RunContext,
        model: str | None = None,
        tools: list[Any] | None = None,
        tool_choice: str | None = None,
    ) -> AIMessage:
        self.calls.append(
            {
                "messages": list(messages),
                "ctx": ctx,
                "model": model,
                "tools": list(tools or []),
                "tool_choice": tool_choice,
            }
        )
        return self.response


class CountingRetriever:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def similarity_search(
        self, query: str, *, tenant_id: str, k: int
    ) -> list[dict[str, Any]]:
        self.calls.append({"query": query, "tenant_id": tenant_id, "k": k})
        return []

    async def close(self) -> None:
        return None


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
            {
                "id": "WO-DEMO-1",
                "tenant_id": "dev",
                "title": "脱敏网络告警",
                "status": "open",
                "priority": "high",
                "assignee_id": "assignee-demo-a",
            },
            {
                "id": "WO-OTHER-1",
                "tenant_id": "other",
                "title": "other",
                "status": "closed",
                "priority": "low",
                "assignee_id": "assignee-demo-b",
            },
        ],
    )
    app.state.bootstrap_data_source = source
    retriever = FakeRetriever()
    import asyncio

    asyncio.run(
        retriever.ingest(
            [
                {
                    "chunk_id": "wo-sop-1",
                    "doc_id": "wo-sop",
                    "text": "show work orders SOP",
                }
            ],
            tenant_id="dev",
        )
    )
    with TestClient(app) as client:
        client.app.state.retriever = retriever
        response = client.post(
            "/chat/stream",
            json={
                "query": "show work orders",
                "thread_id": "wo-1",
                "route": "work_order_ops",
            },
        )

    assert response.status_code == 200
    types = [event["type"] for event in _events(response.text)]
    assert "x.work_order_ops.list" in types
    assert "x.work_order_ops.chart" in types
    assert "x.bridge.citation" in types
    citation = next(
        event
        for event in _events(response.text)
        if event["type"] == "x.bridge.citation"
    )
    assert citation["data"]["citations"][0]["chunk_id"] == "wo-sop-1"
    listing = next(
        event
        for event in _events(response.text)
        if event["type"] == "x.work_order_ops.list"
    )
    assert listing["data"]["rows"] == [
        {
            "id": "WO-DEMO-1",
            "title": "脱敏网络告警",
            "status": "open",
            "priority": "high",
            "assignee_id": "assignee-demo-a",
        }
    ]
    chart = next(
        event
        for event in _events(response.text)
        if event["type"] == "x.work_order_ops.chart"
    )
    option = chart["data"]["echarts_option"]
    assert option == {
        "title": {"text": "按状态统计工单"},
        "tooltip": {"trigger": "axis"},
        "series": [{"name": "工单数", "type": "bar", "data": [1]}],
        "xAxis": {"type": "category", "data": ["open"]},
        "yAxis": {"type": "value", "name": "件"},
    }


def test_structured_draft_drives_preview_approval_and_atomic_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "work-order-structured-secret"
    _configure_real_runtime_auth(monkeypatch, secret=secret)
    from testing.app_factory import create_test_app

    app = create_test_app()
    source = FakeDataSource()
    source.seed(
        "assignees",
        [
            {
                "id": "assignee-rag-demo",
                "tenant_id": "rag-agent-demo",
                "active": True,
            }
        ],
    )
    app.state.bootstrap_data_source = source
    headers = {
        "Authorization": (
            f"Bearer {_token(secret, permissions=ALL_WORK_ORDER_PERMISSIONS)}"
        )
    }
    with TestClient(app) as client:
        response = client.post(
            "/chat/stream",
            headers=headers,
            json={
                "query": "创建工单",
                "thread_id": "wo-structured",
                "route": "work_order_ops",
                "extra": {
                    "work_order_draft": {
                        "title": "园区网络告警",
                        "priority": "high",
                        "assignee_id": "assignee-rag-demo",
                        "ledger_summary": "用户报告园区网络中断，需立即排查",
                    }
                },
            },
        )
        events = _events(response.text)
        preview = next(
            event
            for event in events
            if event["type"] == "x.work_order_ops.ledger_preview"
        )
        required = next(
            event for event in events if event["type"] == "x.bridge.approval_required"
        )
        assert preview["data"]["work_order"]["title"] == "园区网络告警"
        assert preview["data"] == {
            "schema_version": 1,
            "draft_id": preview["data"]["draft_id"],
            "work_order": {
                "title": "园区网络告警",
                "priority": "high",
                "assignee_id": "assignee-rag-demo",
            },
            "ledger": {
                "summary": "用户报告园区网络中断，需立即排查",
                "source": "assistant",
            },
            "approval_required": True,
        }
        assert required["data"]["action"] == {
            "type": "work_order_ops.create_v1",
            "payload": {
                "draft_id": preview["data"]["draft_id"],
                "title": "园区网络告警",
                "priority": "high",
                "assignee_id": "assignee-rag-demo",
                "ledger_summary": "用户报告园区网络中断，需立即排查",
            },
        }
        assert "脱敏工单草稿" not in response.text
        assert awaitable_empty(source, "work_orders")
        approval_id = required["data"]["approval_id"]
        approved = client.post(
            f"/approvals/{approval_id}",
            headers=headers,
            json={"decision": "approve"},
        )
        repeated = client.post(
            f"/approvals/{approval_id}",
            headers=headers,
            json={"decision": "approve"},
        )
    assert approved.status_code == 200
    assert repeated.status_code == 200
    assert source._tables["work_orders"] == [
        {
            "id": f"WO-{approval_id}",
            "tenant_id": "rag-agent-demo",
            "approval_id": approval_id,
            "title": "园区网络告警",
            "status": "open",
            "priority": "high",
            "assignee_id": "assignee-rag-demo",
        }
    ]
    assert source._tables["ledgers"] == [
        {
            "id": f"LG-{approval_id}",
            "tenant_id": "rag-agent-demo",
            "approval_id": approval_id,
            "work_order_id": f"WO-{approval_id}",
            "summary": "用户报告园区网络中断，需立即排查",
        }
    ]


def test_natural_language_draft_uses_only_guarded_prepare_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "work-order-natural-secret"
    _configure_real_runtime_auth(monkeypatch, secret=secret)
    from testing.app_factory import create_test_app

    gateway = DraftGateway(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "prepare_work_order_draft",
                    "args": {
                        "title": "温室设备异常",
                        "priority": "medium",
                        "assignee_id": "assignee-rag-demo",
                        "ledger_summary": "温室传感器连续离线",
                    },
                    "id": "tc-draft-1",
                    "type": "tool_call",
                }
            ],
        )
    )
    source = FakeDataSource()
    source.seed(
        "assignees",
        [
            {
                "id": "assignee-rag-demo",
                "tenant_id": "rag-agent-demo",
                "active": True,
            }
        ],
    )
    app = create_test_app()
    app.state.bootstrap_data_source = source
    headers = {
        "Authorization": (
            f"Bearer {_token(secret, permissions=ALL_WORK_ORDER_PERMISSIONS)}"
        )
    }
    with TestClient(app) as client:
        client.app.state.llm_gateway = gateway
        response = client.post(
            "/chat/stream",
            headers=headers,
            json={
                "query": "请创建一个温室异常工单",
                "thread_id": "wo-natural",
                "route": "work_order_ops",
            },
        )

    assert response.status_code == 200
    assert len(gateway.calls) == 1
    assert [tool.name for tool in gateway.calls[0]["tools"]] == [
        "prepare_work_order_draft"
    ]
    assert gateway.calls[0]["tools"][0] is not prepare_work_order_draft
    assert gateway.calls[0]["tool_choice"] == "prepare_work_order_draft"
    required = next(
        event
        for event in _events(response.text)
        if event["type"] == "x.bridge.approval_required"
    )
    assert required["data"]["action"] == {
        "type": "work_order_ops.create_v1",
        "payload": {
            "draft_id": required["data"]["action"]["payload"]["draft_id"],
            "title": "温室设备异常",
            "priority": "medium",
            "assignee_id": "assignee-rag-demo",
            "ledger_summary": "温室传感器连续离线",
        },
    }


def test_same_thread_read_turn_does_not_reuse_stale_results_or_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "work-order-current-turn-read"
    _configure_real_runtime_auth(monkeypatch, secret=secret)
    from testing.app_factory import create_test_app

    source = FakeDataSource()
    source.seed(
        "assignees",
        [
            {
                "id": "assignee-rag-demo",
                "tenant_id": "rag-agent-demo",
                "active": True,
            }
        ],
    )
    source.seed(
        "work_orders",
        [
            {
                "id": "WO-OLD",
                "tenant_id": "rag-agent-demo",
                "title": "旧工单",
                "status": "open",
                "priority": "low",
                "assignee_id": "assignee-rag-demo",
            }
        ],
    )
    retriever = FakeRetriever()
    import asyncio

    asyncio.run(
        retriever.ingest(
            [
                {
                    "chunk_id": "stale-citation",
                    "doc_id": "stale-doc",
                    "text": "创建工单 演示知识",
                }
            ],
            tenant_id="rag-agent-demo",
        )
    )
    app = create_test_app()
    app.state.bootstrap_data_source = source
    create_headers = {
        "Authorization": (
            f"Bearer {_token(secret, permissions=ALL_WORK_ORDER_PERMISSIONS)}"
        )
    }
    read_headers = {
        "Authorization": (f"Bearer {_token(secret, permissions=['workorder:read'])}")
    }
    with TestClient(app) as client:
        client.app.state.retriever = retriever
        first = client.post(
            "/chat/stream",
            headers=create_headers,
            json={
                "query": "创建工单",
                "thread_id": "wo-current-turn-read",
                "route": "work_order_ops",
                "extra": {
                    "work_order_draft": {
                        "title": "首轮草稿",
                        "priority": "medium",
                        "assignee_id": "assignee-rag-demo",
                        "ledger_summary": "首轮草稿台账",
                    }
                },
            },
        )
        assert "x.bridge.approval_required" in _event_types(first.text)
        first_citation = next(
            event
            for event in _events(first.text)
            if event["type"] == "x.bridge.citation"
        )
        assert first_citation["data"]["citations"][0]["chunk_id"] == "stale-citation"

        source.seed(
            "work_orders",
            [
                {
                    "id": "WO-CURRENT",
                    "tenant_id": "rag-agent-demo",
                    "title": "当前工单",
                    "status": "closed",
                    "priority": "high",
                    "assignee_id": "assignee-rag-demo",
                }
            ],
        )
        second = client.post(
            "/chat/stream",
            headers=read_headers,
            json={
                "query": "show work orders",
                "thread_id": "wo-current-turn-read",
                "route": "work_order_ops",
            },
        )

    second_events = _events(second.text)
    listing = next(
        event for event in second_events if event["type"] == "x.work_order_ops.list"
    )
    citation = next(
        event for event in second_events if event["type"] == "x.bridge.citation"
    )
    assert [row["id"] for row in listing["data"]["rows"]] == ["WO-CURRENT"]
    assert citation["data"]["citations"] == []
    assert "x.work_order_ops.ledger_preview" not in _event_types(second.text)
    assert "x.bridge.approval_required" not in _event_types(second.text)


def test_same_thread_fresh_authorized_draft_uses_current_tool_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "work-order-current-turn-draft"
    _configure_real_runtime_auth(monkeypatch, secret=secret)
    from testing.app_factory import create_test_app

    source = FakeDataSource()
    source.seed(
        "assignees",
        [
            {
                "id": "assignee-rag-demo",
                "tenant_id": "rag-agent-demo",
                "active": True,
            }
        ],
    )
    app = create_test_app()
    app.state.bootstrap_data_source = source
    headers = {
        "Authorization": (
            f"Bearer {_token(secret, permissions=ALL_WORK_ORDER_PERMISSIONS)}"
        )
    }

    def request(title: str, ledger_summary: str) -> dict[str, Any]:
        return {
            "query": "创建工单",
            "thread_id": "wo-current-turn-draft",
            "route": "work_order_ops",
            "extra": {
                "work_order_draft": {
                    "title": title,
                    "priority": "high",
                    "assignee_id": "assignee-rag-demo",
                    "ledger_summary": ledger_summary,
                }
            },
        }

    with TestClient(app) as client:
        first = client.post(
            "/chat/stream",
            headers=headers,
            json=request("首轮园区告警", "首轮园区告警台账"),
        )
        second = client.post(
            "/chat/stream",
            headers=headers,
            json=request("本轮温室告警", "本轮温室告警台账"),
        )

    first_action = next(
        event
        for event in _events(first.text)
        if event["type"] == "x.bridge.approval_required"
    )["data"]["action"]
    second_action = next(
        event
        for event in _events(second.text)
        if event["type"] == "x.bridge.approval_required"
    )["data"]["action"]
    assert first_action["payload"]["title"] == "首轮园区告警"
    assert second_action["payload"] == {
        "draft_id": second_action["payload"]["draft_id"],
        "title": "本轮温室告警",
        "priority": "high",
        "assignee_id": "assignee-rag-demo",
        "ledger_summary": "本轮温室告警台账",
    }
    first_draft_calls = [
        event["data"]["tool_call_id"]
        for event in _events(first.text)
        if event["type"] == "tool_call"
        and event["data"]["name"] == "prepare_work_order_draft"
    ]
    second_draft_calls = [
        event["data"]["tool_call_id"]
        for event in _events(second.text)
        if event["type"] == "tool_call"
        and event["data"]["name"] == "prepare_work_order_draft"
    ]
    assert len(first_draft_calls) == 1
    assert len(second_draft_calls) == 1
    assert first_draft_calls[0] != second_draft_calls[0]


def test_input_builder_copies_only_structured_draft() -> None:
    from domains.work_order_ops.bootstrap import register

    captured: dict[str, Any] = {}

    class Registry:
        def register(self, name: str, value: Any) -> None:
            captured[name] = value

    register(Registry(), Registry(), Registry())
    raw_draft = {
        "title": "园区网络告警",
        "priority": "high",
        "assignee_id": "assignee-rag-demo",
        "ledger_summary": "用户报告园区网络中断，需立即排查",
    }
    graph_input = captured["work_order_ops"](
        "创建工单",
        model="fast",
        extra={
            "work_order_draft": raw_draft,
            "checkpoint_secret": "must-not-be-copied",
        },
    )

    assert graph_input == {
        "messages": [{"role": "user", "content": "创建工单"}],
        "model_alias": "fast",
        "structured_draft": raw_draft,
    }
    assert graph_input["structured_draft"] is not raw_draft


@pytest.mark.parametrize(
    ("permissions", "expected_calls", "forbidden_calls"),
    [
        (
            ["knowledge:read"],
            {"search_work_order_knowledge"},
            {"list_work_orders", "work_order_statistics"},
        ),
        (
            ["workorder:read"],
            {"list_work_orders", "work_order_statistics"},
            {"search_work_order_knowledge"},
        ),
    ],
)
def test_read_tool_visibility_follows_each_permission(
    monkeypatch: pytest.MonkeyPatch,
    permissions: list[str],
    expected_calls: set[str],
    forbidden_calls: set[str],
) -> None:
    secret = "work-order-read-policy-secret"
    _configure_real_runtime_auth(monkeypatch, secret=secret)
    from testing.app_factory import create_test_app

    retriever = CountingRetriever()
    app = create_test_app()
    headers = {"Authorization": f"Bearer {_token(secret, permissions=permissions)}"}
    with TestClient(app) as client:
        client.app.state.retriever = retriever
        response = client.post(
            "/chat/stream",
            headers=headers,
            json={
                "query": "show work orders",
                "thread_id": f"wo-read-policy-{permissions[0]}",
                "route": "work_order_ops",
            },
        )

    calls = set(_tool_call_names(response.text))
    assert expected_calls <= calls
    assert forbidden_calls.isdisjoint(calls)
    if "knowledge:read" not in permissions:
        assert retriever.calls == []


@pytest.mark.parametrize("missing_permission", ["workorder:create", "workorder:assign"])
def test_missing_create_or_assign_hides_draft_tool_and_approval(
    monkeypatch: pytest.MonkeyPatch,
    missing_permission: str,
) -> None:
    secret = f"work-order-{missing_permission}-secret"
    _configure_real_runtime_auth(monkeypatch, secret=secret)
    from testing.app_factory import create_test_app

    gateway = DraftGateway(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "prepare_work_order_draft",
                    "args": {
                        "title": "不应执行的草稿",
                        "priority": "high",
                        "assignee_id": "assignee-rag-demo",
                        "ledger_summary": "不应执行的台账",
                    },
                    "id": "tc-unavailable",
                    "type": "tool_call",
                }
            ],
        )
    )
    permissions = [
        permission
        for permission in ALL_WORK_ORDER_PERMISSIONS
        if permission != missing_permission
    ]
    app = create_test_app()
    headers = {"Authorization": f"Bearer {_token(secret, permissions=permissions)}"}
    with TestClient(app) as client:
        client.app.state.llm_gateway = gateway
        response = client.post(
            "/chat/stream",
            headers=headers,
            json={
                "query": "创建工单",
                "thread_id": f"wo-no-{missing_permission}",
                "route": "work_order_ops",
            },
        )

    assert gateway.calls == []
    assert "prepare_work_order_draft" not in _tool_call_names(response.text)
    assert "x.bridge.approval_required" not in _event_types(response.text)


@pytest.mark.asyncio
async def test_direct_invocation_of_unavailable_draft_tool_is_denied_and_audited() -> (
    None
):
    source = FakeDataSource()
    audit = MemoryAuditLogger()
    ctx = RunContext(
        user_id="draft-denied",
        tenant_id="rag-agent-demo",
        permissions=["workorder:create"],
        metadata={"data_source": source},
    )
    guarded = guard_tools(
        [prepare_work_order_draft],
        policy=RolePolicyEngine(),
        ctx=ctx,
        audit=audit,
    )
    config = {"configurable": {RUN_CONTEXT_KEY: ctx}}

    result = await guarded[0].ainvoke(
        {
            "title": "园区网络告警",
            "priority": "high",
            "assignee_id": "assignee-rag-demo",
            "ledger_summary": "用户报告园区网络中断，需立即排查",
        },
        config=config,
    )

    assert result == "forbidden"
    assert source.last_sql is None
    assert audit.records == [
        {
            "user_id": "draft-denied",
            "tenant_id": "rag-agent-demo",
            "action": "invoke_tool",
            "resource": "prepare_work_order_draft",
            "detail": {
                "decision": "deny",
                "reason_code": "permission_mismatch",
                "policy_version": "role_policy/v1",
            },
            "result": "denied",
        }
    ]


def test_llm_without_draft_tool_call_requests_missing_fields_without_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "work-order-missing-natural-fields"
    _configure_real_runtime_auth(monkeypatch, secret=secret)
    from testing.app_factory import create_test_app

    gateway = DraftGateway(AIMessage(content="我还不能创建这个工单"))
    app = create_test_app()
    headers = {
        "Authorization": (
            f"Bearer {_token(secret, permissions=ALL_WORK_ORDER_PERMISSIONS)}"
        )
    }
    with TestClient(app) as client:
        client.app.state.llm_gateway = gateway
        response = client.post(
            "/chat/stream",
            headers=headers,
            json={
                "query": "创建工单",
                "thread_id": "wo-natural-missing-fields",
                "route": "work_order_ops",
            },
        )

    assert MISSING_FIELDS_MESSAGE in response.text
    assert "x.bridge.approval_required" not in _event_types(response.text)


def test_structured_draft_missing_priority_has_stable_error_and_no_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "work-order-missing-priority"
    _configure_real_runtime_auth(monkeypatch, secret=secret)
    from testing.app_factory import create_test_app

    app = create_test_app()
    headers = {
        "Authorization": (
            f"Bearer {_token(secret, permissions=ALL_WORK_ORDER_PERMISSIONS)}"
        )
    }
    with TestClient(app) as client:
        response = client.post(
            "/chat/stream",
            headers=headers,
            json={
                "query": "创建工单",
                "thread_id": "wo-structured-missing-priority",
                "route": "work_order_ops",
                "extra": {
                    "work_order_draft": {
                        "title": "园区网络告警",
                        "assignee_id": "assignee-rag-demo",
                        "ledger_summary": "用户报告园区网络中断，需立即排查",
                    }
                },
            },
        )

    assert DRAFT_VALIDATION_MESSAGE in response.text
    assert "x.bridge.approval_required" not in _event_types(response.text)
    assert not any(
        event["type"] == "tool_result"
        and event["data"]["name"] == "prepare_work_order_draft"
        for event in _events(response.text)
    )
    assert "validation error" not in response.text.lower()
    assert "field required" not in response.text.lower()
    assert "type=missing" not in response.text.lower()
    assert "input_value" not in response.text.lower()


@pytest.mark.parametrize("path", ["read", "draft"])
def test_backend_query_errors_are_sanitized_in_every_sse_frame(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    secret = f"work-order-backend-sanitize-{path}"
    _configure_real_runtime_auth(monkeypatch, secret=secret)
    from testing.app_factory import create_test_app

    class FailingDataSource(FakeDataSource):
        async def query(self, sql: str, *params: Any) -> list[dict[str, Any]]:
            raise RuntimeError(
                f"secret-marker postgresql://demo:password@db SQL={sql} params={params}"
            )

    app = create_test_app()
    app.state.bootstrap_data_source = FailingDataSource()
    if path == "read":
        permissions = ["workorder:read"]
        body: dict[str, Any] = {
            "query": "show work orders",
            "thread_id": "wo-backend-sanitize-read",
            "route": "work_order_ops",
        }
        expected_summaries = {"work order data unavailable"}
    else:
        permissions = ["workorder:create", "workorder:assign"]
        body = {
            "query": "创建工单",
            "thread_id": "wo-backend-sanitize-draft",
            "route": "work_order_ops",
            "extra": {
                "work_order_draft": {
                    "title": "园区网络告警",
                    "priority": "high",
                    "assignee_id": "assignee-rag-demo",
                    "ledger_summary": "用户报告园区网络中断，需立即排查",
                }
            },
        }
        expected_summaries = {"work order draft validation failed"}
    headers = {"Authorization": f"Bearer {_token(secret, permissions=permissions)}"}

    with TestClient(app) as client:
        response = client.post("/chat/stream", headers=headers, json=body)

    lowered = response.text.lower()
    for unsafe in (
        "secret-marker",
        "postgresql://",
        "password",
        "select *",
        "params=",
    ):
        assert unsafe not in lowered
    summaries = {
        event["data"]["summary"]
        for event in _events(response.text)
        if event["type"] == "tool_result" and not event["data"]["ok"]
    }
    assert summaries
    assert summaries <= expected_summaries
    assert "x.bridge.approval_required" not in _event_types(response.text)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "assignees",
    [
        [],
        [
            {
                "id": "assignee-rag-demo",
                "tenant_id": "other-tenant",
                "active": True,
            }
        ],
        [
            {
                "id": "assignee-rag-demo",
                "tenant_id": "rag-agent-demo",
                "active": False,
            }
        ],
    ],
    ids=["missing", "cross-tenant", "inactive"],
)
async def test_prepare_draft_rejects_unavailable_assignee(
    assignees: list[dict[str, Any]],
) -> None:
    source = FakeDataSource()
    source.seed("assignees", assignees)
    ctx = RunContext(
        tenant_id="rag-agent-demo",
        permissions=["workorder:create", "workorder:assign"],
        metadata={"data_source": source},
    )
    config = {"configurable": {RUN_CONTEXT_KEY: ctx}}

    with pytest.raises(ValueError, match="assignee"):
        await prepare_work_order_draft.ainvoke(
            {
                "title": "园区网络告警",
                "priority": "high",
                "assignee_id": "assignee-rag-demo",
                "ledger_summary": "用户报告园区网络中断，需立即排查",
            },
            config=config,
        )


@pytest.mark.parametrize("active", [False, True], ids=["inactive", "cross-tenant"])
def test_unavailable_structured_assignee_has_no_preview_or_approval(
    monkeypatch: pytest.MonkeyPatch,
    active: bool,
) -> None:
    secret = f"work-order-unavailable-assignee-{active}"
    _configure_real_runtime_auth(monkeypatch, secret=secret)
    from testing.app_factory import create_test_app

    source = FakeDataSource()
    source.seed(
        "assignees",
        [
            {
                "id": "assignee-rag-demo",
                "tenant_id": ("rag-agent-demo" if not active else "other-tenant"),
                "active": active,
            }
        ],
    )
    app = create_test_app()
    app.state.bootstrap_data_source = source
    headers = {
        "Authorization": (
            f"Bearer {_token(secret, permissions=ALL_WORK_ORDER_PERMISSIONS)}"
        )
    }
    with TestClient(app) as client:
        response = client.post(
            "/chat/stream",
            headers=headers,
            json={
                "query": "创建工单",
                "thread_id": f"wo-unavailable-assignee-{active}",
                "route": "work_order_ops",
                "extra": {
                    "work_order_draft": {
                        "title": "园区网络告警",
                        "priority": "high",
                        "assignee_id": "assignee-rag-demo",
                        "ledger_summary": "用户报告园区网络中断，需立即排查",
                    }
                },
            },
        )

    assert DRAFT_VALIDATION_MESSAGE in response.text
    assert "x.work_order_ops.ledger_preview" not in _event_types(response.text)
    assert "x.bridge.approval_required" not in _event_types(response.text)


def awaitable_empty(source: FakeDataSource, table: str) -> bool:
    return source._tables.get(table, []) == []


@pytest.mark.parametrize(
    "query, expected", [("bar", "bar"), ("line trend", "line"), ("pie chart", "pie")]
)
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
    ctx = RunContext(
        tenant_id="acme",
        permissions=["workorder:create", "workorder:assign"],
    )
    first = await handler(action=action, requester_ctx=ctx, approval_id="ap-1")
    second = await handler(action=action, requester_ctx=ctx, approval_id="ap-1")

    assert first == second
    assert (
        len(
            await source.query("SELECT * FROM work_orders WHERE tenant_id = $1", "acme")
        )
        == 1
    )
    assert (
        len(await source.query("SELECT * FROM ledgers WHERE tenant_id = $1", "acme"))
        == 1
    )


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
    assert (
        await source.query("SELECT * FROM work_orders WHERE tenant_id = $1", "acme")
        == []
    )
    assert (
        await source.query("SELECT * FROM ledgers WHERE tenant_id = $1", "acme") == []
    )


@pytest.mark.asyncio
async def test_create_handler_rolls_back_when_ledger_insert_fails() -> None:
    class LedgerFailingDataSource(FakeDataSource):
        async def execute(self, sql: str, *params: Any) -> int:
            if "INSERT INTO ledgers" in sql:
                raise RuntimeError("ledger insert unavailable")
            return await super().execute(sql, *params)

    source = LedgerFailingDataSource()
    source.seed(
        "assignees",
        [{"id": "a1", "tenant_id": "acme", "active": True}],
    )
    action = {
        "type": "work_order_ops.create_v1",
        "payload": {
            "draft_id": "rollback-draft",
            "title": "Synthetic rollback alert",
            "priority": "high",
            "assignee_id": "a1",
            "ledger_summary": "Synthetic rollback ledger",
        },
    }

    with pytest.raises(RuntimeError, match="ledger insert unavailable"):
        await make_create_work_order_handler(source)(
            action=action,
            requester_ctx=RunContext(tenant_id="acme"),
            approval_id="ap-rollback",
        )

    assert await source.query("SELECT * FROM work_orders WHERE tenant_id = $1", "acme") == []
    assert await source.query("SELECT * FROM ledgers WHERE tenant_id = $1", "acme") == []


def test_denying_work_order_approval_performs_no_business_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "work-order-deny-secret"
    _configure_real_runtime_auth(monkeypatch, secret=secret)
    source = FakeDataSource()
    source.seed(
        "assignees",
        [{"id": "assignee-rag-demo", "tenant_id": "rag-agent-demo", "active": True}],
    )
    from testing.app_factory import create_test_app

    app = create_test_app()
    app.state.bootstrap_data_source = source
    headers = {"Authorization": f"Bearer {_token(secret, permissions=ALL_WORK_ORDER_PERMISSIONS)}"}
    body = {
        "query": "创建工单",
        "thread_id": "wo-deny",
        "route": "work_order_ops",
        "extra": {
            "work_order_draft": {
                "title": "拒绝写入验证",
                "priority": "high",
                "assignee_id": "assignee-rag-demo",
                "ledger_summary": "审批拒绝时不得写入",
            }
        },
    }
    with TestClient(app) as client:
        created = client.post("/chat/stream", headers=headers, json=body)
        approval_id = next(
            event["data"]["approval_id"]
            for event in _events(created.text)
            if event["type"] == "x.bridge.approval_required"
        )
        denied = client.post(
            f"/approvals/{approval_id}", headers=headers, json={"decision": "deny"}
        )

    assert denied.status_code == 200
    assert denied.json()["approval"]["status"] == "denied"
    assert awaitable_empty(source, "work_orders")
    assert awaitable_empty(source, "ledgers")
    assert not any(
        event["type"] == "x.work_order_ops.work_order_created"
        for event in _events(created.text)
    )


def test_approval_requires_same_tenant_and_decide_permission_without_business_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "work-order-approval-authorization-secret"
    _configure_real_runtime_auth(monkeypatch, secret=secret)
    source = FakeDataSource()
    source.seed(
        "assignees",
        [{"id": "assignee-rag-demo", "tenant_id": "rag-agent-demo", "active": True}],
    )
    from testing.app_factory import create_test_app

    app = create_test_app()
    app.state.bootstrap_data_source = source
    requester_headers = {
        "Authorization": f"Bearer {_token(secret, permissions=ALL_WORK_ORDER_PERMISSIONS)}"
    }
    body = {
        "query": "创建工单",
        "thread_id": "wo-approval-auth",
        "route": "work_order_ops",
        "extra": {
            "work_order_draft": {
                "title": "审批鉴权验证",
                "priority": "medium",
                "assignee_id": "assignee-rag-demo",
                "ledger_summary": "越权审批不得写入",
            }
        },
    }
    with TestClient(app) as client:
        created = client.post("/chat/stream", headers=requester_headers, json=body)
        approval_id = next(
            event["data"]["approval_id"]
            for event in _events(created.text)
            if event["type"] == "x.bridge.approval_required"
        )
        missing_permission = client.post(
            f"/approvals/{approval_id}",
            headers={
                "Authorization": f"Bearer {_token(secret, permissions=['workorder:create'])}"
            },
            json={"decision": "approve"},
        )
        cross_tenant = client.post(
            f"/approvals/{approval_id}",
            headers={
                "Authorization": f"Bearer {_token(secret, permissions=['approval:decide'], tenant_id='other')}"
            },
            json={"decision": "approve"},
        )

    assert missing_permission.status_code == 403
    assert cross_tenant.status_code == 404
    assert awaitable_empty(source, "work_orders")
    assert awaitable_empty(source, "ledgers")


def test_timeout_and_requester_permission_revocation_do_not_write_work_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "work-order-timeout-and-revocation-secret"
    _configure_real_runtime_auth(monkeypatch, secret=secret)
    source = FakeDataSource()
    source.seed(
        "assignees",
        [{"id": "assignee-rag-demo", "tenant_id": "rag-agent-demo", "active": True}],
    )
    from testing.app_factory import create_test_app

    app = create_test_app()
    app.state.bootstrap_data_source = source
    headers = {"Authorization": f"Bearer {_token(secret, permissions=ALL_WORK_ORDER_PERMISSIONS)}"}

    def create_pending(client: TestClient, thread_id: str) -> str:
        response = client.post(
            "/chat/stream",
            headers=headers,
            json={
                "query": "创建工单",
                "thread_id": thread_id,
                "route": "work_order_ops",
                "extra": {
                    "work_order_draft": {
                        "title": f"{thread_id} 工单",
                        "priority": "high",
                        "assignee_id": "assignee-rag-demo",
                        "ledger_summary": f"{thread_id} 台账",
                    }
                },
            },
        )
        return next(
            event["data"]["approval_id"]
            for event in _events(response.text)
            if event["type"] == "x.bridge.approval_required"
        )

    with TestClient(app) as client:
        timeout_id = create_pending(client, "wo-timeout")
        timeout = client.portal.call(
            lambda: client.app.state.run_lifecycle.finalize_approval(
                approval_id=timeout_id,
                tenant_id="rag-agent-demo",
                decision="deny",
                reason="timeout",
                sink=None,
            )
        )
        revoked_id = create_pending(client, "wo-requester-revoked")
        # The approval snapshot is the authority Lifecycle re-checks at execution.
        client.app.state.approval_store._by_id[revoked_id]["requester_context"][
            "permissions"
        ] = []
        revoked = client.post(
            f"/approvals/{revoked_id}", headers=headers, json={"decision": "approve"}
        )

    assert timeout["status"] == "denied"
    assert timeout["reason"] == "timeout"
    assert revoked.status_code == 200
    assert revoked.json()["approval"]["status"] == "denied"
    assert awaitable_empty(source, "work_orders")
    assert awaitable_empty(source, "ledgers")


def test_concurrent_approve_and_delivery_failure_preserve_one_committed_work_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingEventLog(MemoryEventLog):
        fail_appends = False

        async def append(self, run_id: str, event: dict, *, tenant_id: str) -> None:
            if self.fail_appends:
                raise RuntimeError("event log unavailable")
            await super().append(run_id, event, tenant_id=tenant_id)

    class CapturingSink:
        def __init__(self) -> None:
            self.events: list[dict[str, Any]] = []

        async def emit(self, event: dict[str, Any]) -> None:
            self.events.append(event)

        async def close(self) -> None:
            return None

    secret = "work-order-concurrent-delivery-secret"
    _configure_real_runtime_auth(monkeypatch, secret=secret)
    source = FakeDataSource()
    source.seed(
        "assignees",
        [{"id": "assignee-rag-demo", "tenant_id": "rag-agent-demo", "active": True}],
    )
    from testing.app_factory import create_test_app

    app = create_test_app()
    app.state.bootstrap_data_source = source
    headers = {"Authorization": f"Bearer {_token(secret, permissions=ALL_WORK_ORDER_PERMISSIONS)}"}
    with TestClient(app) as client:
        created = client.post(
            "/chat/stream",
            headers=headers,
            json={
                "query": "创建工单",
                "thread_id": "wo-concurrent-delivery",
                "route": "work_order_ops",
                "extra": {
                    "work_order_draft": {
                        "title": "并发审批工单",
                        "priority": "high",
                        "assignee_id": "assignee-rag-demo",
                        "ledger_summary": "并发审批台账",
                    }
                },
            },
        )
        required = next(
            event
            for event in _events(created.text)
            if event["type"] == "x.bridge.approval_required"
        )
        approval_id = required["data"]["approval_id"]
        run_id = required["run_id"]
        lifecycle = client.app.state.run_lifecycle
        failing_log = FailingEventLog()
        lifecycle._event_log = failing_log

        async def approve_twice() -> list[dict[str, Any]]:
            sinks = [CapturingSink(), CapturingSink()]
            return await asyncio.gather(
                *(
                    lifecycle.finalize_approval(
                        approval_id=approval_id,
                        tenant_id="rag-agent-demo",
                        decision="approve",
                        sink=sink,
                        approver_ctx=RunContext(
                            tenant_id="rag-agent-demo",
                            permissions=["approval:decide"],
                        ),
                    )
                    for sink in sinks
                )
            )

        failing_log.fail_appends = True
        results = client.portal.call(approve_twice)
        stored = client.portal.call(
            lambda: client.app.state.approval_store.get(
                approval_id, tenant_id="rag-agent-demo"
            )
        )
        run = client.portal.call(
            lambda: client.app.state.run_store.get(run_id, tenant_id="rag-agent-demo")
        )

    assert {result["status"] for result in results} <= {"succeeded", "executing"}
    assert stored and stored["status"] == "succeeded"
    assert stored["result_delivery_error"]
    assert run and run["status"] == "done"
    assert run["result_delivery_error"]
    assert len(source._tables["work_orders"]) == 1
    assert len(source._tables["ledgers"]) == 1


def test_old_client_can_ignore_work_order_extensions_and_still_observe_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "0")
    from testing.app_factory import create_test_app

    app = create_test_app()
    with TestClient(app) as client:
        response = client.post(
            "/chat/stream",
            json={
                "query": "show work orders",
                "thread_id": "wo-old-client",
                "route": "work_order_ops",
            },
        )

    stable_types = [
        event["type"]
        for event in _events(response.text)
        if not event["type"].startswith("x.work_order_ops.")
    ]
    assert response.status_code == 200
    assert stable_types[0] == "start"
    assert stable_types[-1] == "done"


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
    error = next(event for event in events if event["type"] == "error")
    assert error["data"] == {"code": "run_failed", "message": "run failed"}
    assert "知识暂不可用" not in response.text
    assert not any(event["type"] == "x.bridge.citation" for event in events)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("AGENTBRIDGE_TEST_PG_DSN"),
    reason="AGENTBRIDGE_TEST_PG_DSN not set",
)
async def test_postgres_approval_recovery_reuses_committed_business_result() -> None:
    import asyncpg
    from adapters.approval_action_registry import ApprovalActionRegistry
    from adapters.postgres_approval_store import PostgresApprovalStore
    from adapters.postgres_data_source import PostgresDataSource

    dsn = os.environ["AGENTBRIDGE_TEST_PG_DSN"]
    migration_dir = Path(__file__).resolve().parents[1] / "migrations"
    connection = await asyncpg.connect(dsn)
    try:
        for filename in (
            "004_approval_execution.sql",
            "005_work_order_ops.sql",
            "006_approval_hardening.sql",
            "007_work_order_demo_tenant.sql",
        ):
            await connection.execute(
                (migration_dir / filename).read_text(encoding="utf-8")
            )
    finally:
        await connection.close()

    approval_id = f"pg-recovery-{os.urandom(8).hex()}"
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
    ctx = RunContext(
        tenant_id="acme",
        permissions=["workorder:create", "workorder:assign"],
    )
    first_source = PostgresDataSource(dsn)
    first_store = PostgresApprovalStore(dsn)
    first_registry = ApprovalActionRegistry()
    first_registry.register(
        "work_order_ops",
        "work_order_ops.create_v1",
        make_create_work_order_handler(first_source),
        {
            "name": "create_work_order",
            "required_permissions_all": ["workorder:create", "workorder:assign"],
        },
    )
    try:
        await first_store.create(
            {
                "approval_id": approval_id,
                "tenant_id": "acme",
                "route": "work_order_ops",
                "run_id": f"run-{approval_id}",
                "thread_id": f"thread-{approval_id}",
                "storage_key": f"acme::thread-{approval_id}",
                "sequence": 1,
                "action": action,
                "requester_context": ctx.model_dump(),
            }
        )
        approved = await first_store.decide(
            approval_id, tenant_id="acme", decision="approve"
        )
        assert approved and approved["status"] == "approved_pending_execution"
        claimed = await first_store.claim_execution(
            approval_id,
            tenant_id="acme",
            now=datetime.now(UTC),
            lease_seconds=0.01,
        )
        assert claimed and claimed["execution_token"]
        first = await first_registry.execute(
            route="work_order_ops",
            action=action,
            requester_ctx=ctx,
            approval_id=approval_id,
        )
    finally:
        await first_source.close()
        await first_store.close()

    second_source = PostgresDataSource(dsn)
    second_store = PostgresApprovalStore(dsn)
    second_registry = ApprovalActionRegistry()
    second_registry.register(
        "work_order_ops",
        "work_order_ops.create_v1",
        make_create_work_order_handler(second_source),
        {
            "name": "create_work_order",
            "required_permissions_all": ["workorder:create", "workorder:assign"],
        },
    )

    class CapturingSink:
        async def emit(self, event: dict[str, Any]) -> None:
            return None

        async def close(self) -> None:
            return None

    second_lifecycle = RunLifecycle(
        locks=InProcessThreadLock(),
        checkpointers=MemoryCheckpointerFactory(),
        graphs=GraphRegistry(),
        tools=ToolRegistry(),
        input_builders=InputBuilderRegistry(),
        runtime=object(),
        cancels=InProcessCancelRegistry(),
        hooks=NoopHooks(),
        event_log=MemoryEventLog(),
        message_store=MemoryMessageStore(),
        run_store=MemoryRunStore(),
        approval_store=second_store,
        approval_executor=second_registry,
        policy=RolePolicyEngine(),
    )
    try:
        await asyncio.sleep(0.02)
        succeeded = await second_lifecycle.finalize_approval(
            approval_id=approval_id,
            tenant_id="acme",
            decision="approve",
            sink=CapturingSink(),
            approver_ctx=RunContext(
                tenant_id="acme", permissions=["approval:decide"]
            ),
        )
        assert succeeded and succeeded["status"] == "succeeded"
        assert len(
            await second_source.query(
                "SELECT * FROM work_orders WHERE approval_id = $1 AND tenant_id = $2",
                approval_id,
                "acme",
            )
        ) == 1
        assert len(
            await second_source.query(
                "SELECT * FROM ledgers WHERE approval_id = $1 AND tenant_id = $2",
                approval_id,
                "acme",
            )
        ) == 1
    finally:
        await second_source.close()
        await second_store.close()
    assert succeeded["result"] == {
        "fragments": [
            {"type": fragment.type, "data": fragment.data} for fragment in first
        ]
    }
