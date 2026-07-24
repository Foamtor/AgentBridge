"""SSE data.agent_id merge from RunContext / fragment."""

from __future__ import annotations

import pytest
from agent_base_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agent_base_core.adapters.inprocess_lock import InProcessThreadLock
from agent_base_core.adapters.noop_hooks import NoopHooks
from agent_base_core.application.run_lifecycle import RunLifecycle
from agent_base_core.protocol.context import RunContext
from agent_base_core.protocol.fragments import OutboundFragment
from agent_base_core.registry.input_builders import InputBuilderRegistry

from fakes import FakeCheckpointerFactory


class _AgentRuntime:
    async def astream(self, builder, **kwargs):
        _ = (builder, kwargs)
        yield OutboundFragment(
            type="text_delta", data={"content": "from-researcher", "agent_id": "researcher"}
        )
        yield OutboundFragment(
            type="text_delta", data={"content": "from-writer", "agent_id": "writer"}
        )


@pytest.mark.asyncio
async def test_emit_merges_agent_id(graphs, tools, queue_and_sink, drain_events) -> None:
    q, sink = queue_and_sink
    lc = RunLifecycle(
        locks=InProcessThreadLock(),
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=_AgentRuntime(),
        cancels=InProcessCancelRegistry(),
        hooks=NoopHooks(),
    )
    await lc.start_stream(
        query="hi",
        thread_id="t-agent",
        route="echo",
        sink=sink,
        ctx=RunContext(tenant_id="t", agent_id="bootstrap"),
    )
    events = await drain_events(q)
    assert events[0]["type"] == "start"
    assert events[0]["data"]["agent_id"] == "bootstrap"
    deltas = [e for e in events if e["type"] == "text_delta"]
    assert deltas[0]["data"]["agent_id"] == "researcher"
    assert deltas[1]["data"]["agent_id"] == "writer"
