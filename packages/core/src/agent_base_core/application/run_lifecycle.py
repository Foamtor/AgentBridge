"""RunLifecycle: lock -> run graph -> emit events -> release."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from agent_base_core.application.graph_config import build_graph_config
from agent_base_core.application.tool_guard import guard_tools
from agent_base_core.errors import RunNotFound, ThreadBusy, UnknownRoute
from agent_base_core.ports.checkpointer import CheckpointerFactory
from agent_base_core.ports.event_sink import EventSink
from agent_base_core.ports.graph_runtime import GraphRuntime
from agent_base_core.ports.hooks import RunHooks
from agent_base_core.ports.run_control import RunCancelRegistry
from agent_base_core.ports.thread_lock import ThreadLock
from agent_base_core.protocol.context import RunContext
from agent_base_core.protocol.events import (
    EVENT_TYPES,
    EXTENSION_TYPE_RE,
    build_event,
    build_extension_event,
)
from agent_base_core.protocol.fragments import OutboundFragment
from agent_base_core.registry.graphs import GraphRegistry
from agent_base_core.registry.input_builders import InputBuilderRegistry
from agent_base_core.registry.tools import ToolRegistry

logger = logging.getLogger(__name__)


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
        self._api_to_storage: dict[str, str] = {}

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

    async def _emit(self, sink: EventSink, evt: dict[str, Any]) -> None:
        if self._event_log is not None:
            await self._event_log.append(evt["run_id"], evt)
        await sink.emit(evt)

    def _storage_key_for_api_thread(self, thread_id: str) -> str:
        return self._api_to_storage.get(thread_id, thread_id)

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
        sequence = 0
        terminal_sent = False
        pre_start_failure = False
        run_ctx = ctx or RunContext()
        run_ctx = run_ctx.model_copy(
            update={"run_id": run_id, "trace_id": run_ctx.trace_id or run_id}
        )
        graph_cfg = build_graph_config(thread_id=thread_id, ctx=run_ctx)
        storage_key = str(graph_cfg["storage_key"])
        self._api_to_storage[thread_id] = storage_key

        if not await self._locks.try_acquire(storage_key, run_id):
            self._api_to_storage.pop(thread_id, None)
            raise ThreadBusy(thread_id)

        cancel_token = asyncio.Event()
        cancelled = False
        await self._cancels.register(storage_key, run_id, cancel_token)
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
                        )
                        terminal_sent = True
                        return
                    sequence += 1
                    await self._emit(sink, evt)
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
                )
                terminal_sent = True
                return

            if cancel_token.is_set():
                cancelled = True

            if cancelled:
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
                )
                terminal_sent = True
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
                )
                terminal_sent = True
        except UnknownRoute:
            pre_start_failure = True
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
                )
                terminal_sent = True
            else:
                pre_start_failure = sequence == 0
                raise
        finally:
            try:
                await self._hooks.on_run_end(
                    {"thread_id": thread_id, "run_id": run_id, "route": route}
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "on_run_end failed thread_id=%s run_id=%s", thread_id, run_id
                )
            await self._locks.release(storage_key, run_id)
            await self._cancels.unregister(storage_key, run_id)
            self._api_to_storage.pop(thread_id, None)
            if not pre_start_failure:
                await sink.close()

    async def cancel(self, *, thread_id: str, run_id: str | None = None) -> None:
        key = self._storage_key_for_api_thread(thread_id)
        ok = await self._cancels.request_cancel(key, run_id)
        if not ok:
            # Fallback: bare key (tests / race before map filled)
            ok = await self._cancels.request_cancel(thread_id, run_id)
        if not ok:
            raise RunNotFound(thread_id)
