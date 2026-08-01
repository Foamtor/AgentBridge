"""AliasLLMGateway tests — swap backends without touching callers."""

from __future__ import annotations

import pytest
from agentbridge_core.adapters.alias_llm_gateway import AliasLLMGateway
from agentbridge_core.adapters.fake_chat_model import FakeChatModel
from agentbridge_core.protocol.context import RunContext


class BindableModel:
    def __init__(self) -> None:
        self.bound: tuple[list[object], str | None] | None = None

    def bind_tools(self, tools, *, tool_choice=None):
        self.bound = (list(tools), tool_choice)
        return self

    async def ainvoke(self, messages):
        return {"messages": list(messages), "bound": self.bound}


@pytest.mark.asyncio
async def test_alias_gateway_switches_model_without_caller_change() -> None:
    fast = FakeChatModel(["from-fast"])
    slow = FakeChatModel(["from-slow"])
    gw = AliasLLMGateway({"default": fast, "slow": slow}, default_alias="default")
    ctx = RunContext()
    messages = [{"role": "user", "content": "q"}]
    assert await gw.chat(messages, ctx=ctx) == "from-fast"
    assert await gw.chat(messages, ctx=ctx, model="slow") == "from-slow"


@pytest.mark.asyncio
async def test_alias_gateway_propagates_tool_binding_to_selected_model() -> None:
    selected = BindableModel()
    gateway = AliasLLMGateway(
        {"default": FakeChatModel(["unused"]), "planner": selected}
    )
    tool = object()
    await gateway.chat(
        [],
        ctx=RunContext(),
        model="planner",
        tools=[tool],
        tool_choice="draft",
    )
    assert selected.bound == ([tool], "draft")
