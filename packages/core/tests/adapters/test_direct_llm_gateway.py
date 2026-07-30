"""DirectLLMGateway tests."""

from __future__ import annotations

import pytest
from agentbridge_core.adapters.direct_llm_gateway import DirectLLMGateway
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
async def test_direct_gateway_chat_delegates_to_model() -> None:
    model = FakeChatModel(["hello"])
    gw = DirectLLMGateway(model)
    ctx = RunContext(tenant_id="t1")
    out = await gw.chat([{"role": "user", "content": "hi"}], ctx=ctx)
    assert out == "hello"
    assert model.calls == [[{"role": "user", "content": "hi"}]]


@pytest.mark.asyncio
async def test_direct_gateway_stream_delegates() -> None:
    model = FakeChatModel(["ab"])
    gw = DirectLLMGateway(model)
    chunks: list[str] = []
    async for c in gw.stream([], ctx=RunContext()):
        chunks.append(c)
    assert "".join(chunks) == "ab"


@pytest.mark.asyncio
async def test_direct_gateway_binds_only_supplied_guarded_tools() -> None:
    model = BindableModel()
    gateway = DirectLLMGateway(model)
    guarded = [object()]
    out = await gateway.chat(
        [{"role": "user", "content": "create"}],
        ctx=RunContext(tenant_id="rag-agent-demo"),
        tools=guarded,
        tool_choice="prepare_work_order_draft",
    )
    assert model.bound == (guarded, "prepare_work_order_draft")
    assert out["bound"] == model.bound


@pytest.mark.asyncio
async def test_direct_gateway_rejects_tools_when_model_cannot_bind() -> None:
    gateway = DirectLLMGateway(FakeChatModel(["unused"]))
    with pytest.raises(RuntimeError, match="llm_tool_binding_unsupported"):
        await gateway.chat([], ctx=RunContext(), tools=[object()])
