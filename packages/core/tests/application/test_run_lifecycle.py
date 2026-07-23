import pytest
from agent_base_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agent_base_core.adapters.inprocess_lock import InProcessThreadLock
from agent_base_core.adapters.noop_hooks import NoopHooks
from agent_base_core.application.errors import ThreadBusy
from agent_base_core.application.run_lifecycle import RunLifecycle
from agent_base_core.registry.input_builders import InputBuilderRegistry


@pytest.mark.asyncio
async def test_start_stream_emits_start_and_done(graphs, tools, queue_and_sink, drain_events):
    from conftest import FakeCheckpointerFactory, FakeRuntime

    q, sink = queue_and_sink
    lc = RunLifecycle(
        locks=InProcessThreadLock(),
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=FakeRuntime(),
        cancels=InProcessCancelRegistry(),
        hooks=NoopHooks(),
    )
    await lc.start_stream(query="hi", thread_id="t1", route="echo", sink=sink)
    types = [e["type"] for e in await drain_events(q)]
    assert types[0] == "start"
    assert types[-1] == "done"


@pytest.mark.asyncio
async def test_thread_busy(graphs, tools, queue_and_sink):
    from conftest import FakeCheckpointerFactory, FakeRuntime

    q, sink = queue_and_sink
    locks = InProcessThreadLock()
    await locks.try_acquire("t1", "other")
    lc = RunLifecycle(
        locks=locks,
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=FakeRuntime(),
        cancels=InProcessCancelRegistry(),
        hooks=NoopHooks(),
    )
    with pytest.raises(ThreadBusy):
        await lc.start_stream(query="hi", thread_id="t1", route="echo", sink=sink)
