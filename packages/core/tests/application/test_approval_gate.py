"""HIL approval gate tests (Plan4 T4 / §4.6)."""

from __future__ import annotations

import asyncio

import pytest
from agentbridge_core.adapters.approval_aware_runtime import ApprovalAwareRuntime
from agentbridge_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agentbridge_core.adapters.inprocess_lock import InProcessThreadLock
from agentbridge_core.adapters.memory_approval_store import MemoryApprovalStore
from agentbridge_core.adapters.memory_audit_logger import MemoryAuditLogger
from agentbridge_core.adapters.memory_event_log import MemoryEventLog
from agentbridge_core.adapters.memory_message_store import MemoryMessageStore
from agentbridge_core.adapters.memory_run_store import MemoryRunStore
from agentbridge_core.adapters.noop_hooks import NoopHooks
from agentbridge_core.adapters.role_policy import RolePolicyEngine
from agentbridge_core.application.run_lifecycle import RunLifecycle
from agentbridge_core.protocol.context import RunContext, checkpoint_thread_key
from agentbridge_core.protocol.fragments import OutboundFragment
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
        approval_executor=kwargs.get("approval_executor"),
        approval_execution_lease_seconds=kwargs.get("approval_execution_lease_seconds", 60.0),
        policy=kwargs.get("policy"),
        audit=kwargs.get("audit"),
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


@pytest.mark.asyncio
async def test_approved_action_executes_once(graphs, tools, queue_and_sink, drain_events) -> None:
    class ActionRuntime:
        async def astream(self, builder, **kwargs):
            yield OutboundFragment(
                type="x.bridge.approval_required",
                data={
                    "tool": "create",
                    "action": {"type": "example.write_v1", "payload": {"x": 1}},
                },
            )

    class Executor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict, str]] = []

        def resource_for(self, *, route: str, action: dict) -> dict:
            return {"name": action["type"]}

        async def execute(self, *, route: str, action: dict, requester_ctx, approval_id: str):
            self.calls.append((route, action, approval_id))
            return [
                OutboundFragment(
                    type="x.example.created", data={"id": action["payload"]["x"]}
                )
            ]

    approvals = MemoryApprovalStore()
    audit = MemoryAuditLogger()
    executor = Executor()
    q, sink = queue_and_sink
    lc = _lc(
        graphs=graphs,
        tools=tools,
        runtime=ActionRuntime(),
        approval_store=approvals,
        approval_executor=executor,
        policy=RolePolicyEngine(),
        audit=audit,
    )
    await lc.start_stream(
        query="write",
        thread_id="t-action-1",
        route="echo",
        sink=sink,
        ctx=RunContext(tenant_id="acme", user_id="requester"),
    )
    required = next(
        event for event in await drain_events(q) if event["type"] == "x.bridge.approval_required"
    )

    class CapturingSink:
        def __init__(self) -> None:
            self.events: list[dict] = []

        async def emit(self, event: dict) -> None:
            self.events.append(event)

        async def close(self) -> None:
            return None

    cap = CapturingSink()
    approval_id = required["data"]["approval_id"]
    await lc.finalize_approval(
        approval_id=approval_id,
        tenant_id="acme",
        decision="approve",
        sink=cap,  # type: ignore[arg-type]
        approver_ctx=RunContext(tenant_id="acme", permissions=["approval:decide"]),
    )
    assert executor.calls == [
        ("echo", {"type": "example.write_v1", "payload": {"x": 1}}, approval_id)
    ]
    assert any(event["type"] == "x.example.created" for event in cap.events)
    assert any(
        record["action"] == "approval_requester_recheck"
        and record["result"] == "allowed"
        for record in audit.records
    )
    stored = await approvals.get(approval_id, tenant_id="acme")
    assert stored and stored["status"] == "succeeded"


@pytest.mark.asyncio
async def test_approved_action_failure_is_persisted_as_retryable(
    graphs, tools, queue_and_sink, drain_events
) -> None:
    class ActionRuntime:
        async def astream(self, builder, **kwargs):
            yield OutboundFragment(
                type="x.bridge.approval_required",
                data={
                    "action": {"type": "example.write_v1", "payload": {"x": 1}},
                },
            )

    class FailingExecutor:
        def resource_for(self, *, route: str, action: dict) -> dict:
            return {"name": action["type"]}

        async def execute(
            self, *, route: str, action: dict, requester_ctx, approval_id: str
        ):
            raise RuntimeError("executor unavailable")

    approvals = MemoryApprovalStore()
    q, sink = queue_and_sink
    lifecycle = _lc(
        graphs=graphs,
        tools=tools,
        runtime=ActionRuntime(),
        approval_store=approvals,
        approval_executor=FailingExecutor(),
        policy=RolePolicyEngine(),
    )
    await lifecycle.start_stream(
        query="write",
        thread_id="t-action-failure",
        route="echo",
        sink=sink,
        ctx=RunContext(tenant_id="acme", user_id="requester"),
    )
    required = next(
        event
        for event in await drain_events(q)
        if event["type"] == "x.bridge.approval_required"
    )

    class CapturingSink:
        def __init__(self) -> None:
            self.events: list[dict] = []

        async def emit(self, event: dict) -> None:
            self.events.append(event)

        async def close(self) -> None:
            return None

    cap = CapturingSink()
    approval_id = required["data"]["approval_id"]
    result = await lifecycle.finalize_approval(
        approval_id=approval_id,
        tenant_id="acme",
        decision="approve",
        sink=cap,  # type: ignore[arg-type]
        approver_ctx=RunContext(
            tenant_id="acme", permissions=["approval:decide"]
        ),
    )

    assert result["status"] == "retryable_failed"
    assert result["error"] == "executor unavailable"
    assert [event["type"] for event in cap.events] == ["error", "done"]


@pytest.mark.asyncio
async def test_invalid_approval_action_has_stable_error_code(
    graphs, tools, queue_and_sink, drain_events
) -> None:
    class InvalidActionRuntime:
        async def astream(self, builder, **kwargs):
            yield OutboundFragment(
                type="x.bridge.approval_required",
                data={"action": {"type": "example.write_v1", "payload": "invalid"}},
            )

    q, sink = queue_and_sink
    lifecycle = _lc(
        graphs=graphs,
        tools=tools,
        runtime=InvalidActionRuntime(),
        approval_store=MemoryApprovalStore(),
    )
    await lifecycle.start_stream(
        query="write",
        thread_id="t-invalid-action",
        route="echo",
        sink=sink,
        ctx=RunContext(tenant_id="acme"),
    )

    error = next(event for event in await drain_events(q) if event["type"] == "error")
    assert error["data"]["code"] == "invalid_approval_action"


@pytest.mark.asyncio
async def test_unregistered_approved_action_is_persisted_as_denied(
    graphs, tools, queue_and_sink, drain_events
) -> None:
    class ActionRuntime:
        async def astream(self, builder, **kwargs):
            yield OutboundFragment(
                type="x.bridge.approval_required",
                data={"action": {"type": "missing.v1", "payload": {}}},
            )

    class MissingExecutor:
        def resource_for(self, *, route, action):
            raise ValueError("no approval action for route")

    approvals = MemoryApprovalStore()
    q, sink = queue_and_sink
    lifecycle = _lc(
        graphs=graphs,
        tools=tools,
        runtime=ActionRuntime(),
        approval_store=approvals,
        approval_executor=MissingExecutor(),
        policy=RolePolicyEngine(),
    )
    await lifecycle.start_stream(
        query="write", thread_id="t-missing-action", route="echo", sink=sink,
        ctx=RunContext(tenant_id="acme", user_id="requester"),
    )
    required = next(
        event for event in await drain_events(q) if event["type"] == "x.bridge.approval_required"
    )

    class CapturingSink:
        def __init__(self) -> None:
            self.events: list[dict] = []

        async def emit(self, event: dict) -> None:
            self.events.append(event)

        async def close(self) -> None:
            return None

    cap = CapturingSink()
    approval_id = required["data"]["approval_id"]
    result = await lifecycle.finalize_approval(
        approval_id=approval_id,
        tenant_id="acme",
        decision="approve",
        sink=cap,  # type: ignore[arg-type]
        approver_ctx=RunContext(tenant_id="acme", permissions=["approval:decide"]),
    )
    assert result["status"] == "denied"
    assert result["reason"] == "approval_handler_not_found"
    assert [event["type"] for event in cap.events] == [
        "x.bridge.approval_resolved", "done"
    ]
