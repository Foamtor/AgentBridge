"""AliasLLMGateway tests — swap backends without touching callers."""

from __future__ import annotations

import pytest
from agent_base_core.adapters.alias_llm_gateway import AliasLLMGateway
from agent_base_core.adapters.fake_chat_model import FakeChatModel
from agent_base_core.protocol.context import RunContext


@pytest.mark.asyncio
async def test_alias_gateway_switches_model_without_caller_change() -> None:
    fast = FakeChatModel(["from-fast"])
    slow = FakeChatModel(["from-slow"])
    gw = AliasLLMGateway({"default": fast, "slow": slow}, default_alias="default")
    ctx = RunContext()
    messages = [{"role": "user", "content": "q"}]
    assert await gw.chat(messages, ctx=ctx) == "from-fast"
    assert await gw.chat(messages, ctx=ctx, model="slow") == "from-slow"
