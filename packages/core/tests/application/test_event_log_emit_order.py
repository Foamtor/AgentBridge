"""append-before-emit ordering and fail-closed behavior."""

from __future__ import annotations

import pytest
from agent_base_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agent_base_core.adapters.inprocess_lock import InProcessThreadLock
from agent_base_core.adapters.memory_event_log import MemoryEventLog
from agent_base_core.adapters.noop_hooks import NoopHooks
from agent_base_core.application.run_lifecycle import RunLifecycle
from agent_base_core.protocol.fragments import OutboundFragment
from agent_base_core.registry.input_builders import InputBuilderRegistry

from conftest import FakeCheckpointerFactory, FakeRuntime


class OrderSink:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.closed = False

    async def emit(self, event: dict) -> None:
        self.events.append(event)

    async def close(self) -> None:
        self.closed = True


class OrderEventLog(MemoryEventLog):
    def __init__(self) -> None:
        super().__init__()
        self.order: list[str] = []

    async def append(self, run_id: str, event: dict) -> None:
        self.order.append(f"append:{event['type']}")
        await super().append(run_id, event)


class TrackingSink(OrderSink):
    def __init__(self, log: OrderEventLog) -> None:
        super().__init__()
        self._log = log

    async def emit(self, event: dict) -> None:
        self._log.order.append(f"emit:{event['type']}")
        await super().emit(event)


class FailingEventLog:
    def __init__(self, *, fail_on: str = "text_delta") -> None:
        self.fail_on = fail_on
        self.appended: list[dict] = []

    async def append(self, run_id: str, event: dict) -> None:
        if event.get("type") == self.fail_on:
            raise RuntimeError("append failed")
        self.appended.append(event)

    async def list(self, run_id: str) -> list[dict]:
        return list(self.appended)


class DeltaRuntime(FakeRuntime):
    async def astream(self, builder, **kwargs):  # noqa: ANN001
        yield OutboundFragment(type="text_delta", data={"content": "secret"})


@pytest.mark.asyncio
async def test_append_before_emit_order(graphs, tools) -> None:
    log = OrderEventLog()
    sink = TrackingSink(log)
    lc = RunLifecycle(
        locks=InProcessThreadLock(),
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=FakeRuntime(),
        cancels=InProcessCancelRegistry(),
        hooks=NoopHooks(),
        event_log=log,
    )
    await lc.start_stream(query="hi", thread_id="t1", route="echo", sink=sink)
    assert log.order[0] == "append:start"
    assert log.order[1] == "emit:start"
    assert "append:text_delta" in log.order
    assert log.order.index("append:text_delta") < log.order.index("emit:text_delta")
    assert log.order[-2] == "append:done"
    assert log.order[-1] == "emit:done"
    stored = await log.list(sink.events[0]["run_id"])
    assert [e["type"] for e in stored] == [e["type"] for e in sink.events]


@pytest.mark.asyncio
async def test_append_failure_does_not_emit_text_delta(graphs, tools) -> None:
    log = FailingEventLog(fail_on="text_delta")
    sink = OrderSink()
    lc = RunLifecycle(
        locks=InProcessThreadLock(),
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=DeltaRuntime(),
        cancels=InProcessCancelRegistry(),
        hooks=NoopHooks(),
        event_log=log,
    )
    await lc.start_stream(query="hi", thread_id="t-fail", route="echo", sink=sink)
    types = [e["type"] for e in sink.events]
    assert types[0] == "start"
    assert "text_delta" not in types
    assert "error" in types
    assert "done" not in types
    assert sink.closed is True
