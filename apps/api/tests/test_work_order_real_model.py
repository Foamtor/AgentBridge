"""The real reference-case path delegates read-tool selection to the model."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from agentbridge_core.protocol.context import RUN_CONTEXT_KEY, RunContext
from domains.work_order_ops.graph import (
    _plan_reads_model,
    _present,
    build_work_order_ops_graph,
)
from domains.work_order_ops.tools import (
    list_work_orders,
    prepare_work_order_draft,
    search_work_order_knowledge,
    work_order_statistics,
)
from langchain_core.messages import AIMessage, ToolMessage


class ReadPlannerGateway:
    def __init__(self) -> None:
        self.tools: list[object] = []
        self.messages: list[object] = []

    async def chat(self, messages, *, ctx, model=None, tools=None, tool_choice=None):
        _ = (ctx, model, tool_choice)
        self.messages = list(messages)
        self.tools = list(tools or [])
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "work_order_statistics",
                    "args": {"dimension": "status"},
                    "id": "tc-real-statistics",
                    "type": "tool_call",
                }
            ],
        )


@pytest.mark.asyncio
async def test_real_case_model_only_sees_guarded_read_tools() -> None:
    gateway = ReadPlannerGateway()
    context = RunContext(
        run_id="real-case",
        metadata={"llm_mode": "openai_compatible", "llm_gateway": gateway},
    )
    guarded_tools = [
        SimpleNamespace(name="work_order_statistics"),
        SimpleNamespace(name="prepare_work_order_draft"),
    ]
    result = await _plan_reads_model(
        {"messages": [{"role": "user", "content": "按状态统计工单"}]},
        {"configurable": {RUN_CONTEXT_KEY: context}},
        guarded_tools=guarded_tools,
        available_names=frozenset({"work_order_statistics"}),
    )

    assert [tool.name for tool in gateway.tools] == ["work_order_statistics"]
    assert result["current_read_call_ids"] == {
        "work_order_statistics:status": "tc-real-statistics"
    }
    assert result["messages"][0].tool_calls[0]["name"] == "work_order_statistics"


@pytest.mark.asyncio
async def test_real_case_uses_published_planner_prompt() -> None:
    class PromptRuntime:
        async def resolve(self, name: str):
            assert name == "work_order_ops.planner"
            return {
                "name": name,
                "content": "Use only tools that are necessary.",
                "source": "platform",
                "version": 3,
            }

    gateway = ReadPlannerGateway()
    context = RunContext(
        run_id="real-case",
        metadata={
            "llm_mode": "openai_compatible",
            "llm_gateway": gateway,
            "prompt_runtime": PromptRuntime(),
        },
    )

    result = await _plan_reads_model(
        {"messages": [{"role": "user", "content": "按状态统计工单"}]},
        {"configurable": {RUN_CONTEXT_KEY: context}},
        guarded_tools=[SimpleNamespace(name="work_order_statistics")],
        available_names=frozenset({"work_order_statistics"}),
    )

    assert gateway.messages == [
        {"role": "system", "content": "Use only tools that are necessary."},
        {"role": "user", "content": "按状态统计工单"},
    ]
    assert context.metadata["prompt_evidence"] == [
        {
            "name": "work_order_ops.planner",
            "source": "platform",
            "version": 3,
        }
    ]
    assert result["prompt_evidence"] == context.metadata["prompt_evidence"]


def test_present_emits_prompt_evidence_from_state() -> None:
    result = _present(
        {
            "messages": [],
            "prompt_evidence": [
                {
                    "name": "work_order_ops.planner",
                    "source": "platform",
                    "version": 3,
                }
            ],
        }
    )
    prompt_event = next(
        item for item in result["outbound_extensions"] if item["type"] == "x.bridge.prompt"
    )
    assert prompt_event["data"]["prompts"][0]["version"] == 3


def test_present_uses_status_statistics_when_model_skips_list_tool() -> None:
    result = _present(
        {
            "messages": [
                ToolMessage(
                    content='{"open": 2, "closed": 1}',
                    tool_call_id="tc-status",
                    name="work_order_statistics",
                )
            ],
            "current_read_call_ids": {
                "work_order_statistics:status": "tc-status"
            },
        }
    )

    chart = next(
        item
        for item in result["outbound_extensions"]
        if item["type"] == "x.work_order_ops.chart"
    )
    assert chart["data"]["x_axis"]["categories"] == ["closed", "open"]
    assert chart["data"]["series"] == [{"name": "工单数", "data": [1, 2]}]


def test_present_for_knowledge_only_hides_unrelated_list_and_chart() -> None:
    result = _present(
        {
            "messages": [
                ToolMessage(
                    content='[{"chunk_id": "sop-1", "text": "Handle safely."}]',
                    tool_call_id="tc-knowledge",
                    name="search_work_order_knowledge",
                )
            ],
            "current_read_call_ids": {
                "search_work_order_knowledge": "tc-knowledge"
            },
        }
    )

    assert [item["type"] for item in result["outbound_extensions"]] == [
        "x.bridge.citation"
    ]


@pytest.mark.asyncio
async def test_real_case_refuses_to_fall_back_to_fake_model() -> None:
    context = RunContext(metadata={"llm_mode": "fake"})
    with pytest.raises(RuntimeError, match="real_model_not_configured"):
        await _plan_reads_model(
            {"messages": [{"role": "user", "content": "查询"}]},
            {"configurable": {RUN_CONTEXT_KEY: context}},
            guarded_tools=[SimpleNamespace(name="list_work_orders")],
            available_names=frozenset({"list_work_orders"}),
        )


@pytest.mark.asyncio
async def test_real_case_falls_back_to_validation_tools_when_model_skips_tool_calls() -> None:
    class NoToolCallGateway:
        async def chat(self, messages, *, ctx, model=None, tools=None, tool_choice=None):
            _ = (messages, ctx, model, tools, tool_choice)
            return AIMessage(content="I will answer without a tool call.")

    class DataSource:
        async def query(self, sql, *params):
            assert params == ("dev",)
            assert "work_orders" in sql
            return [
                {
                    "id": "wo-1",
                    "title": "Network follow-up",
                    "status": "open",
                    "priority": "high",
                    "assignee_id": "assignee-dev-a",
                }
            ]

    context = RunContext(
        run_id="real-fallback",
        tenant_id="dev",
        permissions=["*"],
        metadata={
            "llm_mode": "openai_compatible",
            "llm_gateway": NoToolCallGateway(),
            "data_source": DataSource(),
        },
    )
    graph = build_work_order_ops_graph(
        tools=[
            list_work_orders,
            work_order_statistics,
            search_work_order_knowledge,
            prepare_work_order_draft,
        ]
    )

    result = await graph.ainvoke(
        {
            "messages": [{"role": "user", "content": "show work orders"}],
            "model_alias": "configured-model",
            "use_model_planner": True,
        },
        {"configurable": {RUN_CONTEXT_KEY: context}},
    )

    list_event = next(
        item
        for item in result["outbound_extensions"]
        if item["type"] == "x.work_order_ops.list"
    )
    assert list_event["data"]["rows"] == [
        {
            "id": "wo-1",
            "title": "Network follow-up",
            "status": "open",
            "priority": "high",
            "assignee_id": "assignee-dev-a",
        }
    ]
