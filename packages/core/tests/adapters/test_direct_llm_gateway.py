"""DirectLLMGateway tests."""

from __future__ import annotations

import pytest
from agent_base_core.adapters.direct_llm_gateway import DirectLLMGateway
from agent_base_core.adapters.fake_chat_model import FakeChatModel
from agent_base_core.protocol.context import RunContext


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
