import asyncio

import pytest
from agent_base_core.adapters.event_mapper import (
    map_step_update,
    map_text_delta,
    map_tool_call,
    map_tool_result,
)
from agent_base_core.adapters.sse_event_sink import SseEventSink
from agent_base_core.protocol.fragments import OutboundFragment


@pytest.mark.asyncio
async def test_sse_sink_emit_and_close():
    q: asyncio.Queue = asyncio.Queue()
    sink = SseEventSink(q)
    await sink.emit({"type": "start"})
    await sink.close()
    assert (await q.get())["type"] == "start"
    assert await q.get() is None


def test_map_text_delta():
    frag = map_text_delta("hi")
    assert isinstance(frag, OutboundFragment)
    assert frag.type == "text_delta"
    assert frag.data["content"] == "hi"
    assert not hasattr(frag, "sequence") or "sequence" not in frag.model_dump()


def test_map_tool_call():
    frag = map_tool_call("echo", {"text": "a"}, "tc-1")
    assert frag.type == "tool_call"
    assert frag.data == {"name": "echo", "args": {"text": "a"}, "tool_call_id": "tc-1"}


def test_map_tool_result():
    frag = map_tool_result("echo", ok=True, tool_call_id="tc-1", summary="hello")
    assert frag.type == "tool_result"
    assert frag.data == {
        "name": "echo",
        "ok": True,
        "tool_call_id": "tc-1",
        "summary": "hello",
    }


def test_map_step_update():
    frag = map_step_update("node_a", "running")
    assert frag.type == "step_update"
    assert frag.step == "node_a"
    assert frag.status == "running"
