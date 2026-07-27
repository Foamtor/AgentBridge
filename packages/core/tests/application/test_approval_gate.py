"""HIL approval gate tests (Plan4 T4 / §4.6)."""

from __future__ import annotations

import asyncio

import pytest
from agentbridge_core.adapters.approval_aware_runtime import ApprovalAwareRuntime
from agentbridge_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agentbridge_core.adapters.inprocess_lock import InProcessThreadLock
from agentbridge_core.adapters.memory_approval_store import MemoryApprovalStore
from agentbridge_core.adapters.memory_event_log import MemoryEventLog
from agentbridge_core.adapters.memory_message_store import MemoryMessageStore
from agentbridge_core.adapters.memory_run_store import MemoryRunStore
from agentbridge_core.adapters.noop_hooks import NoopHooks
from agentbridge_core.application.run_lifecycle import RunLifecycle
from agentbridge_core.protocol.context import RunContext, checkpoint_thread_key
from agentbridge_core.registry.input_builders import InputBuilderRegistry

from fakes import FakeCheckpointerFactory


def _lc(**kwargs):
    graphs = kwargs.pop("graphs")
    tools = kwargs.pop("tools")
    return RunLifecycle(
        locks=kwargs.get("locks") or InProcessThreadLock(),
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=kwargs.get("runtime") or ApprovalAwareRuntime(timeout_seconds=60),
        cancels=kwargs.get("cancels") or InProcessCancelRegistry(),
        hooks=NoopHooks(),
        event_log=kwargs.get("event_log") or MemoryEventLog(),
        message_store=kwargs.get("message_store") or MemoryMessageStore(),
        run_store=kwargs.get("run_store") or MemoryRunStore(),
        approval_store=kwargs.get("approval_store") or MemoryApprovalStore(),
    )


@pytest.mark.asyncio
async def test_approval_releases_lock_allows_second_run(
    graphs, tools, queue_and_sink, drain_events
) -> None:
    locks = InProcessThreadLock()
    runs = MemoryRunStore()
    approvals = MemoryApprovalStore()
    q, sink = queue_and_sink
    lc = _lc(
        graphs=graphs,
        tools=tools,
        locks=locks,
        run_store=runs,
        approval_store=approvals,
        runtime=ApprovalAwareRuntime(timeout_seconds=60),
    )
    await lc.start_stream(
        query="write",
        thread_id="t-hil-1",
        route="echo",
        sink=sink,
        ctx=RunContext(tenant_id="acme"),
    )
    events = await drain_events(q)
    assert any(e["type"] == "x.bridge.approval_required" for e in events)
    assert not any(e["type"] == "done" for e in events)
    run_id = events[0]["run_id"]
    run = await runs.get(run_id, tenant_id="acme")
    assert run is not None
    assert run["status"] == "awaiting_approval"
    # Lock released → second run on same API thread must not 409.
    key = checkpoint_thread_key("acme", "t-hil-1")
    assert await locks.try_acquire(key, "r-other")
    await locks.release(key, "r-other")


@pytest.mark.asyncio
async def test_resume_same_run_id(
    graphs, tools, queue_and_sink, drain_events
) -> None:
    locks = InProcessThreadLock()
    runs = MemoryRunStore()
    approvals = MemoryApprovalStore()
    events_log = MemoryEventLog()
    q, sink = queue_and_sink
    lc = _lc(
        graphs=graphs,
        tools=tools,
        locks=locks,
        run_store=runs,
        approval_store=approvals,
        event_log=events_log,
        runtime=ApprovalAwareRuntime(timeout_seconds=60),
    )
    await lc.start_stream(
        query="write",
        thread_id="t-hil-2",
        route="echo",
        sink=sink,
        ctx=RunContext(tenant_id="acme"),
    )
    events = await drain_events(q)
    req = next(e for e in events if e["type"] == "x.bridge.approval_required")
    approval_id = req["data"]["approval_id"]
    run_id = req["run_id"]

    class CapturingSink:
        def __init__(self) -> None:
            self.events: list[dict] = []

        async def emit(self, evt: dict) -> None:
            self.events.append(evt)

        async def close(self) -> None:
            return None

    cap = CapturingSink()
    await lc.finalize_approval(
        approval_id=approval_id,
        tenant_id="acme",
        decision="approve",
        sink=cap,  # type: ignore[arg-type]
    )
    assert any(e["type"] == "x.bridge.approval_resolved" for e in cap.events)
    assert any(e["type"] == "done" for e in cap.events)
    assert all(e["run_id"] == run_id for e in cap.events)
    run = await runs.get(run_id, tenant_id="acme")
    assert run is not None
    assert run["status"] == "done"


@pytest.mark.asyncio
async def test_timeout_denies(graphs, tools, queue_and_sink, drain_events) -> None:
    runs = MemoryRunStore()
    approvals = MemoryApprovalStore()
    events_log = MemoryEventLog()
    q, sink = queue_and_sink
    lc = _lc(
        graphs=graphs,
        tools=tools,
        run_store=runs,
        approval_store=approvals,
        event_log=events_log,
        runtime=ApprovalAwareRuntime(timeout_seconds=0.05),
    )
    await lc.start_stream(
        query="write",
        thread_id="t-hil-3",
        route="echo",
        sink=sink,
        ctx=RunContext(tenant_id="acme"),
    )
    events = await drain_events(q)
    run_id = events[0]["run_id"]
    await asyncio.sleep(0.2)
    logged = await events_log.list(run_id, tenant_id="acme")
    assert any(e["type"] == "x.bridge.approval_resolved" for e in logged)
    resolved = next(e for e in logged if e["type"] == "x.bridge.approval_resolved")
    assert resolved["data"]["decision"] == "deny"
    assert resolved["data"]["reason"] == "timeout"
    assert any(e["type"] == "done" and e.get("data", {}).get("skipped") for e in logged)
    run = await runs.get(run_id, tenant_id="acme")
    assert run is not None
    assert run["status"] == "done"
