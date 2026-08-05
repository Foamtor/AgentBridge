"""The real reference-case path delegates read-tool selection to the model."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from agentbridge_core.protocol.context import RUN_CONTEXT_KEY, RunContext
from domains.work_order_ops.graph import _plan_reads_model
from langchain_core.messages import AIMessage


class ReadPlannerGateway:
    def __init__(self) -> None:
        self.tools: list[object] = []

    async def chat(self, messages, *, ctx, model=None, tools=None, tool_choice=None):
        _ = (messages, ctx, model, tool_choice)
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
        "work_order_statistics": "tc-real-statistics"
    }
    assert result["messages"][0].tool_calls[0]["name"] == "work_order_statistics"


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
