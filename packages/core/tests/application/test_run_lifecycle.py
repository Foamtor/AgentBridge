import asyncio

import pytest
from agent_base_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agent_base_core.adapters.inprocess_lock import InProcessThreadLock
from agent_base_core.adapters.noop_hooks import NoopHooks
from agent_base_core.application.errors import ThreadBusy
from agent_base_core.application.run_lifecycle import RunLifecycle
from agent_base_core.registry.input_builders import InputBuilderRegistry

from conftest import (
    BoomRuntime,
    FakeCheckpointerFactory,
    FakeRuntime,
    SlowCancelRuntime,
)


def _lc(runtime, graphs, tools, locks=None, cancels=None):
    return RunLifecycle(
        locks=locks or InProcessThreadLock(),
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=runtime,
        cancels=cancels or InProcessCancelRegistry(),
        hooks=NoopHooks(),
    )


@pytest.mark.asyncio
async def test_start_stream_emits_start_and_done(graphs, tools, queue_and_sink, drain_events):
    q, sink = queue_and_sink
    lc = _lc(FakeRuntime(), graphs, tools)
    await lc.start_stream(query="hi", thread_id="t1", route="echo", sink=sink)
    events = await drain_events(q)
    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert types[-1] == "done"
    sequences = [e["sequence"] for e in events]
    assert sequences == list(range(1, len(events) + 1))
    assert events[1]["event_id"] == f"{events[1]['run_id']}-2"


@pytest.mark.asyncio
async def test_thread_busy(graphs, tools, queue_and_sink):
    q, sink = queue_and_sink
    locks = InProcessThreadLock()
    await locks.try_acquire("t1", "other")
    lc = _lc(FakeRuntime(), graphs, tools, locks=locks)
    with pytest.raises(ThreadBusy):
        await lc.start_stream(query="hi", thread_id="t1", route="echo", sink=sink)


@pytest.mark.asyncio
async def test_cancel_emits_cancel_events(graphs, tools, queue_and_sink, drain_events):
    q, sink = queue_and_sink
    lc = _lc(SlowCancelRuntime(), graphs, tools)

    async def _run():
        await lc.start_stream(query="hi", thread_id="t-cancel", route="echo", sink=sink)

    task = asyncio.create_task(_run())
    await asyncio.sleep(0.05)
    await lc.cancel(thread_id="t-cancel")
    await task
    types = [e["type"] for e in await drain_events(q)]
    assert types[0] == "start"
    assert "cancel_requested" in types
    assert types[-1] == "cancelled"


@pytest.mark.asyncio
async def test_runtime_error_emits_error_event(graphs, tools, queue_and_sink, drain_events):
    q, sink = queue_and_sink
    lc = _lc(BoomRuntime(), graphs, tools)
    await lc.start_stream(query="hi", thread_id="t-err", route="echo", sink=sink)
    types = [e["type"] for e in await drain_events(q)]
    assert types[0] == "start"
    assert "error" in types
    assert "done" not in types
