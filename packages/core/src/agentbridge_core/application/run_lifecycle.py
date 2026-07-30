"""RunLifecycle: lock -> run graph -> emit events -> release."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from agentbridge_core.application.graph_config import build_graph_config
from agentbridge_core.application.project_turn import project_turn
from agentbridge_core.application.tool_guard import guard_tools
from agentbridge_core.errors import RunNotFound, ThreadBusy, UnknownRoute
from agentbridge_core.ports.checkpointer import CheckpointerFactory
from agentbridge_core.ports.event_sink import EventSink
from agentbridge_core.ports.graph_runtime import GraphRuntime
from agentbridge_core.ports.hooks import RunHooks
from agentbridge_core.ports.run_control import RunCancelRegistry
from agentbridge_core.ports.thread_lock import ThreadLock
from agentbridge_core.protocol.context import RunContext, checkpoint_thread_key
from agentbridge_core.protocol.events import (
    EVENT_TYPES,
    EXTENSION_TYPE_RE,
    build_event,
    build_extension_event,
)
from agentbridge_core.protocol.fragments import OutboundFragment
from agentbridge_core.registry.graphs import GraphRegistry
from agentbridge_core.registry.input_builders import InputBuilderRegistry
from agentbridge_core.registry.tools import ToolRegistry
from contextlib import nullcontext

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventLogAppendError(Exception):
    """Raised when EventLog.append fails; callers must not emit the failed event."""


class RunLifecycle:
    def __init__(
        self,
        locks: ThreadLock,
        checkpointers: CheckpointerFactory,
        graphs: GraphRegistry,
        tools: ToolRegistry,
        input_builders: InputBuilderRegistry,
        runtime: GraphRuntime,
        cancels: RunCancelRegistry,
        hooks: RunHooks,
        policy: Any | None = None,
        audit: Any | None = None,
        event_log: Any | None = None,
        message_store: Any | None = None,
        run_store: Any | None = None,
        metrics: Any | None = None,
        span_factory: Any | None = None,
        approval_store: Any | None = None,
        safety_hooks: Any | None = None,
        approval_executor: Any | None = None,
        approval_execution_lease_seconds: float = 60.0,
    ) -> None:
        self._locks = locks
        self._checkpointers = checkpointers
        self._graphs = graphs
        self._tools = tools
        self._input_builders = input_builders
        self._runtime = runtime
        self._cancels = cancels
        self._hooks = hooks
        self._policy = policy
        self._audit = audit
        self._event_log = event_log
        self._message_store = message_store
        self._run_store = run_store
        self._metrics = metrics
        self._span_factory = span_factory
        self._approval_store = approval_store
        self._safety_hooks = safety_hooks
        self._approval_executor = approval_executor
        self._approval_execution_lease_seconds = approval_execution_lease_seconds

    def replace_runtime(self, runtime: GraphRuntime) -> None:
        """Test/host hook to swap GraphRuntime without private attribute access."""
        self._runtime = runtime

    async def _test_register_cancel(
        self,
        thread_id: str,
        run_id: str,
        token: asyncio.Event | None = None,
    ) -> asyncio.Event:
        """Test-only: pre-register a cancel token without starting a stream."""
        token = token or asyncio.Event()
        await self._cancels.register(thread_id, run_id, token)
        return token

    def _envelope_from_fragment(
        self,
        frag: OutboundFragment,
        *,
        run_id: str,
        sequence: int,
        trace_id: str,
    ) -> dict[str, Any]:
        if frag.type in EVENT_TYPES:
            return build_event(
                frag.type,
                run_id=run_id,
                sequence=sequence,
                trace_id=trace_id,
                data=frag.data,
                step=frag.step,
                status=frag.status,
            )
        if EXTENSION_TYPE_RE.fullmatch(frag.type):
            return build_extension_event(
                frag.type,
                run_id=run_id,
                sequence=sequence,
                trace_id=trace_id,
                data=frag.data,
                step=frag.step,
                status=frag.status,
            )
        raise ValueError(f"invalid outbound fragment type: {frag.type}")

    async def _emit(
        self,
        sink: EventSink,
        evt: dict[str, Any],
        *,
        tenant_id: str,
        agent_id: str = "",
    ) -> None:
        if agent_id:
            data = dict(evt.get("data") or {})
            data.setdefault("agent_id", agent_id)
            evt = dict(evt)
            evt["data"] = data
        if (
            self._safety_hooks is not None
            and evt.get("type") == "text_delta"
            and isinstance(evt.get("data"), dict)
        ):
            data = dict(evt["data"])
            content = data.get("content")
            if content is None:
                content = data.get("text")
            if isinstance(content, str):
                redacted = self._safety_hooks.on_emit_text(content)
                if "content" in data or "text" not in data:
                    data["content"] = redacted
                if "text" in data:
                    data["text"] = redacted
                evt = dict(evt)
                evt["data"] = data
        if self._event_log is not None:
            try:
                await self._event_log.append(
                    evt["run_id"], evt, tenant_id=tenant_id
                )
            except Exception as exc:  # noqa: BLE001 — fail closed on any append error
                raise EventLogAppendError(str(exc)) from exc
        await sink.emit(evt)

    async def _emit_append_failed_error(
        self,
        sink: EventSink,
        *,
        run_id: str,
        sequence: int,
        trace_id: str,
        message: str,
        tenant_id: str,
    ) -> None:
        try:
            await self._emit(
                sink,
                build_event(
                    "error",
                    run_id=run_id,
                    sequence=sequence,
                    trace_id=trace_id,
                    data={"message": message, "code": "event_log_append_failed"},
                ),
                tenant_id=tenant_id,
            )
        except EventLogAppendError:
            logger.exception(
                "event log append failed for error frame run_id=%s", run_id
            )

    async def start_stream(
        self,
        *,
        query: str,
        thread_id: str,
        route: str,
        sink: EventSink,
        model: str | None = None,
        extra: dict[str, Any] | None = None,
        ctx: RunContext | None = None,
        tools_override: list[Any] | None = None,
    ) -> None:
        run_id = f"r-{uuid.uuid4().hex[:12]}"
        trace_id = run_id
        run_ctx = ctx or RunContext()
        run_ctx = run_ctx.model_copy(
            update={"run_id": run_id, "trace_id": run_ctx.trace_id or run_id}
        )
        # Optional ctx is for hosts/tests; tools must use get_run_context(config).
        tenant_id = run_ctx.tenant_id or "default"
        graph_cfg = build_graph_config(thread_id=thread_id, ctx=run_ctx)
        storage_key = str(graph_cfg["storage_key"])

        if not await self._locks.try_acquire(storage_key, run_id):
            raise ThreadBusy(thread_id)

        cancel_token = asyncio.Event()
        await self._cancels.register(storage_key, run_id, cancel_token)
        span_cm: Any = nullcontext()
        if self._span_factory is not None:
            try:
                span_cm = self._span_factory(
                    run_id=run_id, route=route, tenant_id=tenant_id
                )
            except Exception:  # noqa: BLE001 — span must never block runs
                logger.exception(
                    "span_factory failed thread_id=%s run_id=%s", thread_id, run_id
                )
                span_cm = nullcontext()
        body_entered = False
        try:
            with span_cm:
                body_entered = True
                await self._run_stream_body(
                    query=query,
                    thread_id=thread_id,
                    route=route,
                    sink=sink,
                    model=model,
                    extra=extra,
                    run_ctx=run_ctx,
                    tools_override=tools_override,
                    run_id=run_id,
                    trace_id=trace_id,
                    tenant_id=tenant_id,
                    storage_key=storage_key,
                    graph_cfg=graph_cfg,
                    cancel_token=cancel_token,
                )
        except BaseException:
            # span __enter__ failed before body → lock would otherwise stick forever.
            if not body_entered:
                await self._locks.release(storage_key, run_id)
                await self._cancels.unregister(storage_key, run_id)
            raise

    async def _run_stream_body(
        self,
        *,
        query: str,
        thread_id: str,
        route: str,
        sink: EventSink,
        model: str | None,
        extra: dict[str, Any] | None,
        run_ctx: RunContext,
        tools_override: list[Any] | None,
        run_id: str,
        trace_id: str,
        tenant_id: str,
        storage_key: str,
        graph_cfg: dict[str, Any],
        cancel_token: asyncio.Event,
    ) -> None:
        sequence = 0
        terminal_sent = False
        terminal_status: str | None = None
        pre_start_failure = False
        cancelled = False
        awaiting_approval = False
        lock_held = True
        agent_id = run_ctx.agent_id or ""
        try:
            builder = self._graphs.get(route)
            if tools_override is not None:
                tools: Any = tools_override
            else:
                try:
                    tools = self._tools.get(route)
                except UnknownRoute:
                    tools = []
            if not isinstance(tools, list):
                tools = list(tools) if tools else []
            if self._policy is not None:
                tools = guard_tools(
                    tools, policy=self._policy, ctx=run_ctx, audit=self._audit
                )
            try:
                input_builder = self._input_builders.get(route)
                graph_input = input_builder(query, model=model, extra=extra or {})
            except UnknownRoute:
                graph_input = {"messages": [query]}

            sequence += 1
            await self._emit(
                sink,
                build_event(
                    "start",
                    run_id=run_id,
                    sequence=sequence,
                    trace_id=trace_id,
                    data={"thread_id": thread_id, "route": route},
                ),
                tenant_id=tenant_id,
                agent_id=agent_id,
            )
            if self._run_store is not None:
                await self._run_store.upsert(
                    {
                        "run_id": run_id,
                        "tenant_id": tenant_id,
                        "thread_id": thread_id,
                        "route": route,
                        "started_at": _utc_now_iso(),
                        "status": "pending",
                    }
                )

            checkpointer = await self._checkpointers.get()

            try:
                async for frag in self._runtime.astream(
                    builder,
                    tools=tools,
                    checkpointer=checkpointer,
                    thread_id=storage_key,
                    query=query,
                    cancel_token=cancel_token,
                    extra={
                        **(extra or {}),
                        "run_id": run_id,
                        "trace_id": trace_id,
                        "graph_input": graph_input,
                        "model": model,
                        "run_context": run_ctx,
                        "graph_config": graph_cfg,
                        "api_thread_id": thread_id,
                        "storage_key": storage_key,
                    },
                ):
                    if cancel_token.is_set():
                        cancelled = True
                        break
                    try:
                        if not isinstance(frag, OutboundFragment):
                            raise TypeError(
                                f"runtime must yield OutboundFragment, got {type(frag)!r}"
                            )
                        evt = self._envelope_from_fragment(
                            frag, run_id=run_id, sequence=sequence + 1, trace_id=trace_id
                        )
                    except (ValueError, TypeError) as exc:
                        sequence += 1
                        await self._emit(
                            sink,
                            build_event(
                                "error",
                                run_id=run_id,
                                sequence=sequence,
                                trace_id=trace_id,
                                data={
                                    "message": str(exc),
                                    "code": "invalid_event_type",
                                },
                            ),
                            tenant_id=tenant_id,
                        )
                        terminal_sent = True
                        terminal_status = "error"
                        return
                    sequence += 1
                    frag_agent = ""
                    if isinstance(frag.data, dict) and frag.data.get("agent_id"):
                        frag_agent = str(frag.data["agent_id"])
                        agent_id = frag_agent
                    if (
                        frag.type == "x.bridge.approval_required"
                        and self._approval_store is not None
                    ):
                        await self._pause_for_approval(
                            frag=frag,
                            evt=evt,
                            sink=sink,
                            run_id=run_id,
                            trace_id=trace_id,
                            tenant_id=tenant_id,
                            thread_id=thread_id,
                            storage_key=storage_key,
                            route=route,
                            query=query,
                            sequence=sequence,
                            requester_ctx=run_ctx,
                        )
                        awaiting_approval = True
                        lock_held = False
                        break
                    await self._emit(
                        sink, evt, tenant_id=tenant_id, agent_id=agent_id
                    )
            except EventLogAppendError as exc:
                sequence += 1
                await self._emit_append_failed_error(
                    sink,
                    run_id=run_id,
                    sequence=sequence,
                    trace_id=trace_id,
                    message=str(exc),
                    tenant_id=tenant_id,
                )
                terminal_sent = True
                terminal_status = "error"
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception("run failed thread_id=%s run_id=%s", thread_id, run_id)
                sequence += 1
                await self._emit(
                    sink,
                    build_event(
                        "error",
                        run_id=run_id,
                        sequence=sequence,
                        trace_id=trace_id,
                        data={"message": str(exc), "code": "run_failed"},
                    ),
                    tenant_id=tenant_id,
                )
                terminal_sent = True
                terminal_status = "error"
                return

            if cancel_token.is_set():
                cancelled = True

            if awaiting_approval:
                pass
            elif cancelled:
                sequence += 1
                await self._emit(
                    sink,
                    build_event(
                        "cancel_requested",
                        run_id=run_id,
                        sequence=sequence,
                        trace_id=trace_id,
                        data={"thread_id": thread_id, "run_id": run_id},
                    ),
                    tenant_id=tenant_id,
                )
                sequence += 1
                await self._emit(
                    sink,
                    build_event(
                        "cancelled",
                        run_id=run_id,
                        sequence=sequence,
                        trace_id=trace_id,
                        data={"thread_id": thread_id, "run_id": run_id},
                    ),
                    tenant_id=tenant_id,
                )
                terminal_sent = True
                terminal_status = "cancelled"
            else:
                sequence += 1
                await self._emit(
                    sink,
                    build_event(
                        "done",
                        run_id=run_id,
                        sequence=sequence,
                        trace_id=trace_id,
                    ),
                    tenant_id=tenant_id,
                )
                terminal_sent = True
                terminal_status = "done"
        except UnknownRoute:
            pre_start_failure = True
            raise
        except EventLogAppendError as exc:
            if not terminal_sent and sequence > 0:
                sequence += 1
                await self._emit_append_failed_error(
                    sink,
                    run_id=run_id,
                    sequence=sequence,
                    trace_id=trace_id,
                    message=str(exc),
                    tenant_id=tenant_id,
                )
                terminal_sent = True
                terminal_status = "error"
            else:
                pre_start_failure = sequence == 0
                raise
        except Exception as exc:  # noqa: BLE001
            if not terminal_sent and sequence > 0:
                logger.exception(
                    "run failed after start thread_id=%s run_id=%s", thread_id, run_id
                )
                sequence += 1
                await self._emit(
                    sink,
                    build_event(
                        "error",
                        run_id=run_id,
                        sequence=sequence,
                        trace_id=trace_id,
                        data={"message": str(exc), "code": "run_failed"},
                    ),
                    tenant_id=tenant_id,
                )
                terminal_sent = True
                terminal_status = "error"
            else:
                pre_start_failure = sequence == 0
                raise
        finally:
            if (
                terminal_sent
                and terminal_status
                and self._event_log is not None
                and self._message_store is not None
                and self._run_store is not None
            ):
                try:
                    await project_turn(
                        event_log=self._event_log,
                        message_store=self._message_store,
                        run_store=self._run_store,
                        tenant_id=tenant_id,
                        thread_id=thread_id,
                        run_id=run_id,
                        query=query,
                        terminal=terminal_status,
                    )
                except Exception:  # noqa: BLE001 — never block cleanup
                    logger.exception(
                        "project_turn failed thread_id=%s run_id=%s", thread_id, run_id
                    )
            try:
                await self._hooks.on_run_end(
                    {"thread_id": thread_id, "run_id": run_id, "route": route}
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "on_run_end failed thread_id=%s run_id=%s", thread_id, run_id
                )
            if self._metrics is not None:
                try:
                    self._metrics.inc(
                        "agentbridge_runs_total", labels={"route": route}
                    )
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "metrics.inc failed thread_id=%s run_id=%s", thread_id, run_id
                    )
            if lock_held:
                await self._locks.release(storage_key, run_id)
            await self._cancels.unregister(storage_key, run_id)
            if not pre_start_failure:
                await sink.close()

    async def _pause_for_approval(
        self,
        *,
        frag: OutboundFragment,
        evt: dict[str, Any],
        sink: EventSink,
        run_id: str,
        trace_id: str,
        tenant_id: str,
        thread_id: str,
        storage_key: str,
        route: str,
        query: str,
        sequence: int,
        requester_ctx: RunContext,
    ) -> str:
        assert self._approval_store is not None
        data = dict(frag.data or {})
        action = data.get("action")
        if action is not None and (
            not isinstance(action, dict)
            or not isinstance(action.get("type"), str)
            or not action["type"].strip()
            or not isinstance(action.get("payload"), dict)
        ):
            raise ValueError("invalid_approval_action")
        timeout_seconds = float(data.get("timeout_seconds") or 30.0)
        approval_id = await self._approval_store.create(
            {
                "tenant_id": tenant_id,
                "thread_id": thread_id,
                "storage_key": storage_key,
                "run_id": run_id,
                "trace_id": trace_id,
                "sequence": sequence,
                "route": route,
                "query": query,
                "tool": data.get("tool"),
                "action": action,
                "requester_context": _approval_requester_snapshot(requester_ctx),
                "timeout_seconds": timeout_seconds,
                "status": "pending",
            }
        )
        evt_data = dict(evt.get("data") or {})
        evt_data.update(
            {
                "approval_id": approval_id,
                "run_id": run_id,
                "tool": data.get("tool"),
                "timeout_seconds": timeout_seconds,
            }
        )
        evt = dict(evt)
        evt["data"] = evt_data
        await self._emit(sink, evt, tenant_id=tenant_id)
        if self._run_store is not None:
            await self._run_store.upsert(
                {
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "thread_id": thread_id,
                    "status": "awaiting_approval",
                    "approval_id": approval_id,
                    "storage_key": storage_key,
                }
            )
        await self._locks.release(storage_key, run_id)
        asyncio.create_task(
            self._approval_timeout(approval_id, tenant_id, timeout_seconds)
        )
        return approval_id

    async def _approval_timeout(
        self, approval_id: str, tenant_id: str, delay: float
    ) -> None:
        try:
            await asyncio.sleep(delay)
            await self.finalize_approval(
                approval_id=approval_id,
                tenant_id=tenant_id,
                decision="deny",
                sink=None,
                reason="timeout",
            )
        except Exception:  # noqa: BLE001
            logger.exception("approval timeout handler failed id=%s", approval_id)

    async def finalize_approval(
        self,
        *,
        approval_id: str,
        tenant_id: str,
        decision: str,
        sink: EventSink | None,
        reason: str | None = None,
        approver_ctx: RunContext | None = None,
    ) -> dict[str, Any]:
        """Resolve pending approval (approve/deny/timeout); re-acquire storage_key.

        Acquire lock first so HTTP resume can 409 while still pending. Timeout that
        cannot acquire (new run holds the lock) still force-claims and writes EventLog.
        """
        if self._approval_store is None:
            raise RuntimeError("approval_store not configured")
        rec = await self._approval_store.get(approval_id, tenant_id=tenant_id)
        if rec is None:
            raise RunNotFound(approval_id)
        if rec.get("action") is not None:
            return await self._finalize_action_approval(
                rec=rec,
                approval_id=approval_id,
                tenant_id=tenant_id,
                decision=decision,
                sink=sink,
                reason=reason,
                approver_ctx=approver_ctx,
            )
        if rec.get("status") != "pending":
            return rec
        storage_key = str(rec["storage_key"])
        run_id = str(rec["run_id"])
        thread_id = str(rec["thread_id"])
        trace_id = str(rec.get("trace_id") or run_id)
        sequence = int(rec.get("sequence") or 0)
        query = str(rec.get("query") or "")

        acquired = await self._locks.try_acquire(storage_key, run_id)
        if not acquired:
            if reason != "timeout":
                raise ThreadBusy(thread_id)
            logger.warning(
                "approval timeout without lock approval_id=%s run_id=%s",
                approval_id,
                run_id,
            )

        class _NullSink:
            async def emit(self, evt: dict[str, Any]) -> None:
                return None

            async def close(self) -> None:
                return None

        out_sink: EventSink = sink if sink is not None else _NullSink()  # type: ignore[assignment]
        try:
            updated = await self._approval_store.resolve(
                approval_id, tenant_id=tenant_id, decision=decision
            )
            if updated is None:
                existing = await self._approval_store.get(
                    approval_id, tenant_id=tenant_id
                )
                return existing or rec
            sequence += 1
            resolved = build_extension_event(
                "x.bridge.approval_resolved",
                run_id=run_id,
                sequence=sequence,
                trace_id=trace_id,
                data={
                    "approval_id": approval_id,
                    "decision": decision,
                    "reason": reason or decision,
                    "skipped": decision != "approve",
                },
            )
            await self._emit(out_sink, resolved, tenant_id=tenant_id)
            if decision == "approve":
                sequence += 1
                await self._emit(
                    out_sink,
                    build_event(
                        "tool_result",
                        run_id=run_id,
                        sequence=sequence,
                        trace_id=trace_id,
                        data={
                            "ok": True,
                            "summary": f"approved:{rec.get('tool')}",
                        },
                    ),
                    tenant_id=tenant_id,
                )
            sequence += 1
            await self._emit(
                out_sink,
                build_event(
                    "done",
                    run_id=run_id,
                    sequence=sequence,
                    trace_id=trace_id,
                    data={
                        "skipped": decision != "approve",
                        "approval_decision": decision,
                    },
                ),
                tenant_id=tenant_id,
            )
            if (
                self._event_log is not None
                and self._message_store is not None
                and self._run_store is not None
            ):
                await project_turn(
                    event_log=self._event_log,
                    message_store=self._message_store,
                    run_store=self._run_store,
                    tenant_id=tenant_id,
                    thread_id=thread_id,
                    run_id=run_id,
                    query=query,
                    terminal="done",
                )
            return updated
        finally:
            if acquired:
                await self._locks.release(storage_key, run_id)

    async def _finalize_action_approval(
        self,
        *,
        rec: dict[str, Any],
        approval_id: str,
        tenant_id: str,
        decision: str,
        sink: EventSink | None,
        reason: str | None,
        approver_ctx: RunContext | None,
    ) -> dict[str, Any]:
        """Resolve and execute a persisted action without rebuilding its payload."""
        assert self._approval_store is not None
        storage_key = str(rec["storage_key"])
        run_id = str(rec["run_id"])
        trace_id = str(rec.get("trace_id") or run_id)
        sequence = int(rec.get("sequence") or 0)
        route = str(rec.get("route") or "")
        action = dict(rec["action"])

        class _NullSink:
            async def emit(self, evt: dict[str, Any]) -> None:
                return None

            async def close(self) -> None:
                return None

        out_sink: EventSink = sink if sink is not None else _NullSink()  # type: ignore[assignment]
        acquired = await self._locks.try_acquire(storage_key, run_id)
        if not acquired and reason != "timeout":
            raise ThreadBusy(str(rec["thread_id"]))
        try:
            status = rec.get("status")
            if status == "executing":
                recovered = await self._approval_store.recover_expired_execution(
                    approval_id, tenant_id=tenant_id, now=datetime.now(timezone.utc)
                )
                if recovered is None:
                    return rec
                rec = recovered
                status = rec.get("status")
            if status == "pending":
                updated = await self._approval_store.decide(
                    approval_id, tenant_id=tenant_id, decision=decision, reason=reason
                )
                if updated is None:
                    return rec
                rec = updated
                if decision != "approve":
                    sequence += 1
                    await self._emit(out_sink, build_extension_event("x.bridge.approval_resolved", run_id=run_id, sequence=sequence, trace_id=trace_id, data={"approval_id": approval_id, "decision": decision, "reason": reason or decision, "skipped": True}), tenant_id=tenant_id)
                    sequence += 1
                    await self._emit(out_sink, build_event("done", run_id=run_id, sequence=sequence, trace_id=trace_id, data={"skipped": True, "approval_decision": decision}), tenant_id=tenant_id)
                    return rec
            elif status not in {"approved_pending_execution", "retryable_failed"}:
                return rec

            sequence += 1
            if decision != "approve":
                await self._emit(
                    out_sink,
                    build_extension_event(
                        "x.bridge.approval_resolved",
                        run_id=run_id,
                        sequence=sequence,
                        trace_id=trace_id,
                        data={"approval_id": approval_id, "decision": decision, "reason": reason or decision, "skipped": True},
                    ),
                    tenant_id=tenant_id,
                )
                sequence += 1
                await self._emit(out_sink, build_event("done", run_id=run_id, sequence=sequence, trace_id=trace_id, data={"skipped": True, "approval_decision": decision}), tenant_id=tenant_id)
                return rec

            deny_reason: str | None = None
            if approver_ctx is None or (
                "*" not in approver_ctx.permissions
                and "approval:decide" not in approver_ctx.permissions
            ):
                deny_reason = "approver_permission_denied"
            elif self._approval_executor is None:
                deny_reason = "approval_handler_not_found"
            else:
                requester_ctx = RunContext.model_validate(rec.get("requester_context") or {})
                resource = self._approval_executor.resource_for(route=route, action=action)
                if self._policy is not None and self._policy.decide(
                    ctx=requester_ctx, action="invoke_tool", resource=resource
                ) != "allow":
                    deny_reason = "requester_policy_denied"
            if deny_reason is not None:
                updated = await self._approval_store.mark_execution_denied(
                    approval_id, tenant_id=tenant_id, reason=deny_reason
                )
                sequence += 1
                await self._emit(out_sink, build_extension_event("x.bridge.approval_resolved", run_id=run_id, sequence=sequence, trace_id=trace_id, data={"approval_id": approval_id, "decision": "approve", "reason": deny_reason, "skipped": True}), tenant_id=tenant_id)
                sequence += 1
                await self._emit(out_sink, build_event("done", run_id=run_id, sequence=sequence, trace_id=trace_id, data={"skipped": True, "approval_decision": "approve"}), tenant_id=tenant_id)
                return updated or rec

            claimed = await self._approval_store.claim_execution(
                approval_id,
                tenant_id=tenant_id,
                now=datetime.now(timezone.utc),
                lease_seconds=self._approval_execution_lease_seconds,
            )
            if claimed is None:
                return await self._approval_store.get(approval_id, tenant_id=tenant_id) or rec
            try:
                fragments = await self._approval_executor.execute(
                    route=route,
                    action=action,
                    requester_ctx=RunContext.model_validate(rec.get("requester_context") or {}),
                    approval_id=approval_id,
                )
            except Exception as exc:  # noqa: BLE001
                await self._approval_store.mark_retryable_failed(approval_id, tenant_id=tenant_id, error=str(exc))
                sequence += 1
                await self._emit(out_sink, build_event("error", run_id=run_id, sequence=sequence, trace_id=trace_id, data={"code": "approval_execution_failed", "message": str(exc)}), tenant_id=tenant_id)
                sequence += 1
                await self._emit(out_sink, build_event("done", run_id=run_id, sequence=sequence, trace_id=trace_id, data={"approval_decision": "approve", "status": "error"}, status="error"), tenant_id=tenant_id)
                return await self._approval_store.get(approval_id, tenant_id=tenant_id) or rec
            updated = await self._approval_store.mark_succeeded(
                approval_id,
                tenant_id=tenant_id,
                result={"fragments": [{"type": item.type, "data": item.data} for item in fragments]},
            )
            sequence += 1
            await self._emit(out_sink, build_extension_event("x.bridge.approval_resolved", run_id=run_id, sequence=sequence, trace_id=trace_id, data={"approval_id": approval_id, "decision": "approve", "reason": "approve", "skipped": False}), tenant_id=tenant_id)
            for fragment in fragments:
                sequence += 1
                await self._emit(out_sink, self._envelope_from_fragment(fragment, run_id=run_id, sequence=sequence, trace_id=trace_id), tenant_id=tenant_id)
            sequence += 1
            await self._emit(out_sink, build_event("done", run_id=run_id, sequence=sequence, trace_id=trace_id, data={"skipped": False, "approval_decision": "approve"}), tenant_id=tenant_id)
            return updated or rec
        finally:
            if acquired:
                await self._locks.release(storage_key, run_id)


def _approval_requester_snapshot(ctx: RunContext) -> dict[str, Any]:
    """Persist only authorization-relevant requester fields, never metadata."""
    return {
        "user_id": ctx.user_id,
        "tenant_id": ctx.tenant_id,
        "roles": list(ctx.roles),
        "permissions": list(ctx.permissions),
        "max_tokens": ctx.max_tokens,
        "max_tool_calls": ctx.max_tool_calls,
        "deadline_ms": ctx.deadline_ms,
        "policy_bundle_version": ctx.policy_bundle_version,
    }

    async def cancel(
        self,
        *,
        thread_id: str,
        run_id: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        key = checkpoint_thread_key(tenant_id or "default", thread_id)
        ok = await self._cancels.request_cancel(key, run_id)
        if not ok:
            raise RunNotFound(thread_id)
