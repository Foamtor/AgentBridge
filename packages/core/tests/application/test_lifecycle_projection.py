"""Lifecycle projects messages after terminal when stores are wired."""

from __future__ import annotations

import pytest
from agentbridge_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agentbridge_core.adapters.inprocess_lock import InProcessThreadLock
from agentbridge_core.adapters.memory_event_log import MemoryEventLog
from agentbridge_core.adapters.memory_message_store import MemoryMessageStore
from agentbridge_core.adapters.memory_run_store import MemoryRunStore
from agentbridge_core.adapters.noop_hooks import NoopHooks
from agentbridge_core.application.run_lifecycle import RunLifecycle
from agentbridge_core.protocol.context import RunContext
from agentbridge_core.registry.input_builders import InputBuilderRegistry

from fakes import FakeCheckpointerFactory, FakeRuntime


class CollectSink:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def emit(self, event: dict) -> None:
        self.events.append(event)

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_lifecycle_projects_after_done(graphs, tools) -> None:
    event_log = MemoryEventLog()
    messages = MemoryMessageStore()
    runs = MemoryRunStore()
    lc = RunLifecycle(
        locks=InProcessThreadLock(),
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=FakeRuntime(),
        cancels=InProcessCancelRegistry(),
        hooks=NoopHooks(),
        event_log=event_log,
        message_store=messages,
        run_store=runs,
    )
    sink = CollectSink()
    await lc.start_stream(
        query="hello",
        thread_id="th-proj",
        route="echo",
        sink=sink,
        ctx=RunContext(tenant_id="acme", user_id="u1"),
    )
    msgs = await messages.list_messages("acme", "th-proj")
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "ok"
    run_id = sink.events[0]["run_id"]
    assert (await runs.get(run_id, tenant_id="acme"))["status"] == "done"
    assert await messages.list_messages("other", "th-proj") == []
