import asyncio

import pytest
from agent_base_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agent_base_core.adapters.inprocess_lock import InProcessThreadLock
from agent_base_core.adapters.noop_hooks import NoopHooks
from agent_base_core.application.errors import ThreadBusy
from agent_base_core.application.run_lifecycle import RunLifecycle
from agent_base_core.protocol.context import checkpoint_thread_key
from agent_base_core.registry.input_builders import InputBuilderRegistry

from fakes import (
    BadExtensionRuntime,
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
    await locks.try_acquire(checkpoint_thread_key("default", "t1"), "other")
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
async def test_cancel_uses_tenant_storage_key_not_bare_thread(
    graphs, tools, queue_and_sink, drain_events
) -> None:
    """Two tenants can share api thread_id; cancel must hit the right storage_key."""
    from agent_base_core.application.errors import RunNotFound
    from agent_base_core.protocol.context import RunContext

    q, sink = queue_and_sink
    lc = _lc(SlowCancelRuntime(), graphs, tools)

    async def _run():
        await lc.start_stream(
            query="hi",
            thread_id="shared-tid",
            route="echo",
            sink=sink,
            ctx=RunContext(tenant_id="tenant-a", user_id="u1"),
        )

    task = asyncio.create_task(_run())
    await asyncio.sleep(0.05)
    with pytest.raises(RunNotFound):
        await lc.cancel(thread_id="shared-tid", tenant_id="tenant-b")
    await lc.cancel(thread_id="shared-tid", tenant_id="tenant-a")
    await task
    types = [e["type"] for e in await drain_events(q)]
    assert "cancelled" in types


@pytest.mark.asyncio
async def test_runtime_error_emits_error_event(graphs, tools, queue_and_sink, drain_events):
    q, sink = queue_and_sink
    lc = _lc(BoomRuntime(), graphs, tools)
    await lc.start_stream(query="hi", thread_id="t-err", route="echo", sink=sink)
    types = [e["type"] for e in await drain_events(q)]
    assert types[0] == "start"
    assert "error" in types
    assert "done" not in types


@pytest.mark.asyncio
async def test_cancel_events_include_thread_and_run_id(
    graphs, tools, queue_and_sink, drain_events
):
    q, sink = queue_and_sink
    lc = _lc(SlowCancelRuntime(), graphs, tools)

    async def _run():
        await lc.start_stream(query="hi", thread_id="t-cancel-data", route="echo", sink=sink)

    task = asyncio.create_task(_run())
    await asyncio.sleep(0.05)
    await lc.cancel(thread_id="t-cancel-data")
    await task
    events = await drain_events(q)
    cancel_evts = [e for e in events if e["type"] in {"cancel_requested", "cancelled"}]
    assert len(cancel_evts) == 2
    for e in cancel_evts:
        assert e["data"]["thread_id"] == "t-cancel-data"
        assert e["data"]["run_id"] == e["run_id"]


@pytest.mark.asyncio
async def test_invalid_extension_type_emits_error(
    graphs, tools, queue_and_sink, drain_events
):
    q, sink = queue_and_sink
    lc = _lc(BadExtensionRuntime(), graphs, tools)
    await lc.start_stream(query="hi", thread_id="t-bad-x", route="echo", sink=sink)
    events = await drain_events(q)
    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert "error" in types
    assert "done" not in types
    assert types[-1] == "error"


@pytest.mark.asyncio
async def test_hooks_failure_still_releases_lock(graphs, tools, queue_and_sink, drain_events):
    class BoomHooks:
        async def on_run_end(self, payload):
            raise RuntimeError("hooks boom")

    q, sink = queue_and_sink
    locks = InProcessThreadLock()
    lc = RunLifecycle(
        locks=locks,
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=FakeRuntime(),
        cancels=InProcessCancelRegistry(),
        hooks=BoomHooks(),
    )
    await lc.start_stream(query="hi", thread_id="t-hooks", route="echo", sink=sink)
    events = await drain_events(q)
    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "done"
    # Lock must be free for a second acquire (same storage_key as lifecycle).
    key = checkpoint_thread_key("default", "t-hooks")
    assert await locks.try_acquire(key, "r-next")
    await locks.release(key, "r-next")


@pytest.mark.asyncio
async def test_span_enter_failure_still_releases_lock(
    graphs, tools, queue_and_sink
) -> None:
    from contextlib import contextmanager

    @contextmanager
    def boom_span(*, run_id: str, route: str, tenant_id: str):
        raise RuntimeError("span enter boom")
        yield  # pragma: no cover

    q, sink = queue_and_sink
    locks = InProcessThreadLock()
    lc = RunLifecycle(
        locks=locks,
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=FakeRuntime(),
        cancels=InProcessCancelRegistry(),
        hooks=NoopHooks(),
        span_factory=boom_span,
    )
    with pytest.raises(RuntimeError, match="span enter boom"):
        await lc.start_stream(query="hi", thread_id="t-span", route="echo", sink=sink)
    key = checkpoint_thread_key("default", "t-span")
    assert await locks.try_acquire(key, "r-next")
    await locks.release(key, "r-next")
