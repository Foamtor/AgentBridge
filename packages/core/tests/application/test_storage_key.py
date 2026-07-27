"""storage_key used for lock + cancel + runtime thread_id."""

from __future__ import annotations

import pytest
from agentbridge_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agentbridge_core.adapters.inprocess_lock import InProcessThreadLock
from agentbridge_core.adapters.noop_hooks import NoopHooks
from agentbridge_core.application.errors import ThreadBusy
from agentbridge_core.application.graph_config import build_graph_config
from agentbridge_core.application.run_lifecycle import RunLifecycle
from agentbridge_core.protocol.context import RunContext, checkpoint_thread_key
from agentbridge_core.protocol.fragments import OutboundFragment
from agentbridge_core.registry.input_builders import InputBuilderRegistry

from fakes import FakeCheckpointerFactory, FakeRuntime


class RecordingLock(InProcessThreadLock):
    def __init__(self) -> None:
        super().__init__()
        self.acquired_keys: list[str] = []

    async def try_acquire(self, thread_id: str, run_id: str) -> bool:
        self.acquired_keys.append(thread_id)
        return await super().try_acquire(thread_id, run_id)


class RecordingRuntime(FakeRuntime):
    def __init__(self) -> None:
        self.last_thread_id: str | None = None
        self.last_extra: dict | None = None

    async def astream(self, builder, **kwargs):  # noqa: ANN001
        self.last_thread_id = kwargs.get("thread_id")
        self.last_extra = kwargs.get("extra")
        yield OutboundFragment(type="text_delta", data={"content": "ok"})


def test_build_graph_config_storage_key_matches_checkpoint_helper() -> None:
    ctx = RunContext(tenant_id="acme", user_id="u1")
    cfg = build_graph_config(thread_id="t-1", ctx=ctx)
    assert cfg["storage_key"] == checkpoint_thread_key("acme", "t-1")
    assert cfg["configurable"]["thread_id"] == cfg["storage_key"]


@pytest.mark.asyncio
async def test_lifecycle_lock_and_runtime_use_storage_key(graphs, tools, queue_and_sink) -> None:
    locks = RecordingLock()
    runtime = RecordingRuntime()
    lc = RunLifecycle(
        locks=locks,
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=runtime,
        cancels=InProcessCancelRegistry(),
        hooks=NoopHooks(),
    )
    q, sink = queue_and_sink
    ctx = RunContext(tenant_id="tenant-a", user_id="u1")
    await lc.start_stream(
        query="hi", thread_id="api-t1", route="echo", sink=sink, ctx=ctx
    )
    expected = checkpoint_thread_key("tenant-a", "api-t1")
    assert locks.acquired_keys == [expected]
    assert runtime.last_thread_id == expected
    assert runtime.last_extra is not None
    assert runtime.last_extra["storage_key"] == expected
    assert runtime.last_extra["api_thread_id"] == "api-t1"


@pytest.mark.asyncio
async def test_same_api_thread_different_tenant_no_lock_collision() -> None:
    locks = InProcessThreadLock()
    assert await locks.try_acquire(checkpoint_thread_key("t1", "same"), "r1")
    assert not await locks.try_acquire(checkpoint_thread_key("t1", "same"), "r2")
    assert await locks.try_acquire(checkpoint_thread_key("t2", "same"), "r3")


@pytest.mark.asyncio
async def test_thread_busy_uses_storage_key(graphs, tools, queue_and_sink) -> None:
    locks = InProcessThreadLock()
    key = checkpoint_thread_key("default", "busy-t")
    await locks.try_acquire(key, "existing")
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
    _, sink = queue_and_sink
    with pytest.raises(ThreadBusy):
        await lc.start_stream(query="x", thread_id="busy-t", route="echo", sink=sink)
