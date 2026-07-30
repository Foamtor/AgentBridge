"""HIL approval gate tests (Plan4 T4 / §4.6)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

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
from agentbridge_core.errors import ApprovalStateConflict, KnowledgeBackendUnavailable
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


class _CapturingSink:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def emit(self, event: dict) -> None:
        self.events.append(event)

    async def close(self) -> None:
        return None


class _ActionRuntime:
    async def astream(self, builder, **kwargs):
        yield OutboundFragment(
            type="x.bridge.approval_required",
            data={
                "timeout_seconds": 3600,
                "action": {"type": "example.write_v1", "payload": {"x": 1}},
            },
        )


class _ScriptedExecutor:
    def __init__(self, outcomes: list[Exception | list[OutboundFragment]]) -> None:
        self._outcomes = outcomes

    def resource_for(self, *, route: str, action: dict) -> dict:
        return {"name": action["type"]}

    async def execute(
        self, *, route: str, action: dict, requester_ctx, approval_id: str
    ) -> list[OutboundFragment]:
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


async def _start_action(
    lifecycle: RunLifecycle,
    *,
    queue,
    sink,
    drain_events,
    thread_id: str,
    requester_ctx: RunContext | None = None,
) -> tuple[str, str]:
    await lifecycle.start_stream(
        query="write",
        thread_id=thread_id,
        route="echo",
        sink=sink,
        ctx=requester_ctx or RunContext(tenant_id="acme", user_id="requester"),
    )
    required = next(
        event
        for event in await drain_events(queue)
        if event["type"] == "x.bridge.approval_required"
    )
    return required["data"]["approval_id"], required["run_id"]


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


@pytest.mark.asyncio
async def test_retryable_action_failure_then_success_has_monotonic_events_and_one_projection(
    graphs, tools, queue_and_sink, drain_events
) -> None:
    approvals = MemoryApprovalStore()
    event_log = MemoryEventLog()
    runs = MemoryRunStore()
    messages = MemoryMessageStore()
    executor = _ScriptedExecutor(
        [
            RuntimeError(
                "database unavailable at postgresql://admin:secret@db/private"
            ),
            [
                OutboundFragment(
                    type="x.example.created",
                    data={"id": 1},
                )
            ],
        ]
    )
    queue, sink = queue_and_sink
    lifecycle = _lc(
        graphs=graphs,
        tools=tools,
        runtime=_ActionRuntime(),
        approval_store=approvals,
        approval_executor=executor,
        policy=RolePolicyEngine(),
        event_log=event_log,
        run_store=runs,
        message_store=messages,
    )
    approval_id, run_id = await _start_action(
        lifecycle,
        queue=queue,
        sink=sink,
        drain_events=drain_events,
        thread_id="t-action-retry",
    )
    approver = RunContext(
        tenant_id="acme", permissions=["approval:decide"]
    )

    first_sink = _CapturingSink()
    first = await lifecycle.finalize_approval(
        approval_id=approval_id,
        tenant_id="acme",
        decision="approve",
        sink=first_sink,  # type: ignore[arg-type]
        approver_ctx=approver,
    )

    assert first["status"] == "retryable_failed"
    error_event = next(event for event in first_sink.events if event["type"] == "error")
    assert error_event["data"] == {
        "code": "approval_execution_failed",
        "message": "approved action execution failed",
    }
    assert await messages.list_messages("acme", "t-action-retry") == []
    failed_run = await runs.get(run_id, tenant_id="acme")
    assert failed_run and failed_run["status"] == "error"

    second = await lifecycle.finalize_approval(
        approval_id=approval_id,
        tenant_id="acme",
        decision="approve",
        sink=_CapturingSink(),  # type: ignore[arg-type]
        approver_ctx=approver,
    )

    assert second["status"] == "succeeded"
    logged = await event_log.list(run_id, tenant_id="acme")
    sequences = [event["sequence"] for event in logged]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))
    assert any(event["type"] == "error" for event in logged)
    assert any(event["type"] == "x.example.created" for event in logged)
    succeeded_run = await runs.get(run_id, tenant_id="acme")
    assert succeeded_run and succeeded_run["status"] == "done"
    projected = await messages.list_messages("acme", "t-action-retry")
    assert [message["role"] for message in projected] == ["user", "assistant"]

    repeated = await lifecycle.finalize_approval(
        approval_id=approval_id,
        tenant_id="acme",
        decision="approve",
        sink=_CapturingSink(),  # type: ignore[arg-type]
        approver_ctx=approver,
    )
    assert repeated["status"] == "succeeded"
    assert len(await messages.list_messages("acme", "t-action-retry")) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("decision", "reason"),
    [("deny", None), ("deny", "timeout")],
)
async def test_action_deny_and_timeout_project_terminal_turn_once(
    graphs, tools, queue_and_sink, drain_events, decision, reason
) -> None:
    event_log = MemoryEventLog()
    runs = MemoryRunStore()
    messages = MemoryMessageStore()
    queue, sink = queue_and_sink
    lifecycle = _lc(
        graphs=graphs,
        tools=tools,
        runtime=_ActionRuntime(),
        approval_store=MemoryApprovalStore(),
        approval_executor=_ScriptedExecutor([]),
        event_log=event_log,
        run_store=runs,
        message_store=messages,
    )
    thread_id = f"t-action-{reason or decision}"
    approval_id, run_id = await _start_action(
        lifecycle,
        queue=queue,
        sink=sink,
        drain_events=drain_events,
        thread_id=thread_id,
    )

    denied = await lifecycle.finalize_approval(
        approval_id=approval_id,
        tenant_id="acme",
        decision=decision,
        reason=reason,
        sink=_CapturingSink(),  # type: ignore[arg-type]
    )

    assert denied["status"] == "denied"
    run = await runs.get(run_id, tenant_id="acme")
    assert run and run["status"] == "done"
    projected = await messages.list_messages("acme", thread_id)
    assert [message["role"] for message in projected] == ["user", "assistant"]

    await lifecycle.finalize_approval(
        approval_id=approval_id,
        tenant_id="acme",
        decision=decision,
        reason=reason,
        sink=_CapturingSink(),  # type: ignore[arg-type]
    )
    assert len(await messages.list_messages("acme", thread_id)) == 2


@pytest.mark.asyncio
async def test_requester_policy_denial_projects_terminal_turn(
    graphs, tools, queue_and_sink, drain_events
) -> None:
    class PermissionedExecutor(_ScriptedExecutor):
        def resource_for(self, *, route: str, action: dict) -> dict:
            return {
                "name": action["type"],
                "required_permissions": ["example:write"],
            }

    runs = MemoryRunStore()
    messages = MemoryMessageStore()
    queue, sink = queue_and_sink
    lifecycle = _lc(
        graphs=graphs,
        tools=tools,
        runtime=_ActionRuntime(),
        approval_store=MemoryApprovalStore(),
        approval_executor=PermissionedExecutor([]),
        policy=RolePolicyEngine(),
        event_log=MemoryEventLog(),
        run_store=runs,
        message_store=messages,
    )
    approval_id, run_id = await _start_action(
        lifecycle,
        queue=queue,
        sink=sink,
        drain_events=drain_events,
        thread_id="t-action-policy-denied",
    )

    denied = await lifecycle.finalize_approval(
        approval_id=approval_id,
        tenant_id="acme",
        decision="approve",
        sink=_CapturingSink(),  # type: ignore[arg-type]
        approver_ctx=RunContext(
            tenant_id="acme", permissions=["approval:decide"]
        ),
    )

    assert denied["status"] == "denied"
    assert denied["reason"] == "requester_policy_denied"
    run = await runs.get(run_id, tenant_id="acme")
    assert run and run["status"] == "done"
    projected = await messages.list_messages("acme", "t-action-policy-denied")
    assert [message["role"] for message in projected] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_retryable_deny_transitions_but_executing_deny_conflicts(
    graphs, tools
) -> None:
    approvals = MemoryApprovalStore()
    base = {
        "tenant_id": "acme",
        "thread_id": "t-decision",
        "storage_key": checkpoint_thread_key("acme", "t-decision"),
        "run_id": "r-decision",
        "trace_id": "r-decision",
        "sequence": 2,
        "route": "echo",
        "query": "write",
        "action": {"type": "example.write_v1", "payload": {"x": 1}},
        "requester_context": {"tenant_id": "acme"},
    }
    retryable_id = await approvals.create(
        {**base, "approval_id": "ap-retryable", "status": "approved_pending_execution"}
    )
    retryable_claim = await approvals.claim_execution(
        retryable_id,
        tenant_id="acme",
        now=datetime.now(timezone.utc),
        lease_seconds=60,
    )
    assert retryable_claim
    assert await approvals.mark_retryable_failed(
        retryable_id,
        tenant_id="acme",
        execution_token=retryable_claim["execution_token"],
        error="temporary",
    )
    executing_id = await approvals.create(
        {
            **base,
            "approval_id": "ap-executing",
            "run_id": "r-executing",
            "status": "approved_pending_execution",
        }
    )
    assert await approvals.claim_execution(
        executing_id,
        tenant_id="acme",
        now=datetime.now(timezone.utc),
        lease_seconds=60,
    )
    locks = InProcessThreadLock()
    lifecycle = _lc(
        graphs=graphs,
        tools=tools,
        locks=locks,
        approval_store=approvals,
        approval_executor=_ScriptedExecutor([]),
    )

    retryable_sink = _CapturingSink()
    denied = await lifecycle.finalize_approval(
        approval_id=retryable_id,
        tenant_id="acme",
        decision="deny",
        sink=retryable_sink,  # type: ignore[arg-type]
        approver_ctx=RunContext(
            tenant_id="acme", permissions=["approval:decide"]
        ),
    )

    assert denied["status"] == "denied"
    assert not any(
        event["type"] == "x.example.created" for event in retryable_sink.events
    )

    executing_sink = _CapturingSink()
    assert await locks.try_acquire(base["storage_key"], "active-worker")
    try:
        with pytest.raises(ApprovalStateConflict):
            await lifecycle.finalize_approval(
                approval_id=executing_id,
                tenant_id="acme",
                decision="deny",
                sink=executing_sink,  # type: ignore[arg-type]
                approver_ctx=RunContext(
                    tenant_id="acme", permissions=["approval:decide"]
                ),
            )
    finally:
        await locks.release(base["storage_key"], "active-worker")
    assert not any(
        event["type"] == "x.example.created" for event in executing_sink.events
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_kind", "expected_code", "expected_message"),
    [
        (
            "knowledge",
            "knowledge_backend_unavailable",
            "knowledge backend unavailable",
        ),
        (
            "tool_binding",
            "llm_tool_binding_unsupported",
            "configured model does not support tool binding",
        ),
        ("generic", "run_failed", "run failed"),
    ],
)
async def test_lifecycle_dependency_errors_are_stable_and_safe(
    graphs,
    tools,
    queue_and_sink,
    drain_events,
    failure_kind,
    expected_code,
    expected_message,
) -> None:
    secret = "postgresql://admin:secret@db/private SELECT password"
    if failure_kind == "knowledge":
        failure = KnowledgeBackendUnavailable(secret)
    elif failure_kind == "tool_binding":
        failure = RuntimeError("llm_tool_binding_unsupported")
    else:
        failure = RuntimeError(secret)

    class FailingRuntime:
        async def astream(self, builder, **kwargs):
            raise failure
            yield  # pragma: no cover

    queue, sink = queue_and_sink
    lifecycle = _lc(
        graphs=graphs,
        tools=tools,
        runtime=FailingRuntime(),
    )
    await lifecycle.start_stream(
        query="write",
        thread_id=f"t-safe-error-{failure_kind}",
        route="echo",
        sink=sink,
        ctx=RunContext(tenant_id="acme"),
    )

    event = next(
        item for item in await drain_events(queue) if item["type"] == "error"
    )
    assert event["data"] == {
        "code": expected_code,
        "message": expected_message,
    }
    assert "secret" not in str(event)
    assert "SELECT" not in str(event)


@pytest.mark.asyncio
@pytest.mark.parametrize("stale_finish", ["succeeded", "retryable_failed"])
async def test_stale_action_worker_emits_no_terminal_business_events(
    graphs, tools, queue_and_sink, drain_events, stale_finish
) -> None:
    class StaleFinishStore(MemoryApprovalStore):
        async def mark_succeeded(self, *args, **kwargs):
            if stale_finish == "succeeded":
                return None
            return await super().mark_succeeded(*args, **kwargs)

        async def mark_retryable_failed(self, *args, **kwargs):
            if stale_finish == "retryable_failed":
                return None
            return await super().mark_retryable_failed(*args, **kwargs)

    outcome: Exception | list[OutboundFragment]
    if stale_finish == "succeeded":
        outcome = [
            OutboundFragment(type="x.example.created", data={"id": 1})
        ]
    else:
        outcome = RuntimeError("database unavailable")
    approvals = StaleFinishStore()
    queue, sink = queue_and_sink
    lifecycle = _lc(
        graphs=graphs,
        tools=tools,
        runtime=_ActionRuntime(),
        approval_store=approvals,
        approval_executor=_ScriptedExecutor([outcome]),
        policy=RolePolicyEngine(),
    )
    approval_id, _ = await _start_action(
        lifecycle,
        queue=queue,
        sink=sink,
        drain_events=drain_events,
        thread_id=f"t-stale-{stale_finish}",
    )
    result_sink = _CapturingSink()

    result = await lifecycle.finalize_approval(
        approval_id=approval_id,
        tenant_id="acme",
        decision="approve",
        sink=result_sink,  # type: ignore[arg-type]
        approver_ctx=RunContext(
            tenant_id="acme", permissions=["approval:decide"]
        ),
    )

    latest = await approvals.get(approval_id, tenant_id="acme")
    assert result == latest
    assert latest and latest["status"] == "executing"
    assert not any(
        event["type"]
        in {
            "error",
            "done",
            "x.bridge.approval_resolved",
            "x.example.created",
        }
        for event in result_sink.events
    )


@pytest.mark.asyncio
async def test_result_delivery_failure_projects_success_and_preserves_safe_run_error(
    graphs, tools, queue_and_sink, drain_events
) -> None:
    class ToggleEventLog(MemoryEventLog):
        fail_appends = False

        async def append(self, run_id, event, *, tenant_id):
            if self.fail_appends:
                raise RuntimeError(
                    "postgresql://admin:secret@db/private INSERT failed"
                )
            await super().append(run_id, event, tenant_id=tenant_id)

    approvals = MemoryApprovalStore()
    event_log = ToggleEventLog()
    runs = MemoryRunStore()
    messages = MemoryMessageStore()
    queue, sink = queue_and_sink
    lifecycle = _lc(
        graphs=graphs,
        tools=tools,
        runtime=_ActionRuntime(),
        approval_store=approvals,
        approval_executor=_ScriptedExecutor(
            [[OutboundFragment(type="x.example.created", data={"id": 1})]]
        ),
        policy=RolePolicyEngine(),
        event_log=event_log,
        run_store=runs,
        message_store=messages,
    )
    approval_id, run_id = await _start_action(
        lifecycle,
        queue=queue,
        sink=sink,
        drain_events=drain_events,
        thread_id="t-delivery-error",
    )
    event_log.fail_appends = True
    result_sink = _CapturingSink()

    result = await lifecycle.finalize_approval(
        approval_id=approval_id,
        tenant_id="acme",
        decision="approve",
        sink=result_sink,  # type: ignore[arg-type]
        approver_ctx=RunContext(
            tenant_id="acme", permissions=["approval:decide"]
        ),
    )

    assert result["status"] == "succeeded"
    assert result["result_delivery_error"]
    public_error = next(
        event for event in result_sink.events if event["type"] == "error"
    )
    assert public_error["data"] == {
        "code": "approval_result_delivery_failed",
        "message": "approved action result delivery failed",
        "business_completed": True,
    }
    run = await runs.get(run_id, tenant_id="acme")
    assert run and run["status"] == "done"
    assert run["result_delivery_error"] == "approved action result delivery failed"
    projected = await messages.list_messages("acme", "t-delivery-error")
    assert [message["role"] for message in projected] == ["user", "assistant"]
