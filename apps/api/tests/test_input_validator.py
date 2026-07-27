"""InputValidator plugin → HTTP 400 invalid_input."""

from __future__ import annotations

import pytest
from agentbridge_core.adapters.basic_input_validator import BasicInputValidator
from agentbridge_core.application.pipeline import InputValidatorPlugin, PipelineRequest
from agentbridge_core.errors import InvalidInput
from agentbridge_core.protocol.context import RunContext


@pytest.mark.asyncio
async def test_basic_validator_rejects_long_query() -> None:
    v = BasicInputValidator(max_len=5)
    with pytest.raises(ValueError, match="query too long"):
        v.validate_query("abcdef")


@pytest.mark.asyncio
async def test_basic_validator_strips_nul() -> None:
    v = BasicInputValidator()
    assert v.validate_query("a\x00b") == "ab"


@pytest.mark.asyncio
async def test_input_validator_plugin_raises_invalid_input() -> None:
    plugin = InputValidatorPlugin(BasicInputValidator(max_len=3))
    req = PipelineRequest(
        query="toolong",
        thread_id="t",
        route="echo",
        sink=None,  # type: ignore[arg-type]
        ctx=RunContext(),
    )
    with pytest.raises(InvalidInput, match="query too long"):
        await plugin.before_run(req)


def test_chat_stream_invalid_input_400(client) -> None:
    r = client.post(
        "/chat/stream",
        json={"query": "x" * 8001, "thread_id": "t-iv", "route": "echo"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_input"
