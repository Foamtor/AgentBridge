import asyncio

import pytest
from agent_base_core.adapters.event_mapper import map_text_delta
from agent_base_core.adapters.sse_event_sink import SseEventSink


@pytest.mark.asyncio
async def test_sse_sink_emit_and_close():
    q: asyncio.Queue = asyncio.Queue()
    sink = SseEventSink(q)
    await sink.emit({"type": "start"})
    await sink.close()
    assert (await q.get())["type"] == "start"
    assert await q.get() is None


def test_map_text_delta():
    evt = map_text_delta("hi", run_id="r1", sequence=2, trace_id="tr1")
    assert evt["type"] == "text_delta"
    assert evt["data"]["content"] == "hi"
