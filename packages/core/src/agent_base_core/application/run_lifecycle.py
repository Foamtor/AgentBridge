"""RunLifecycle: lock -> run graph -> emit events -> release."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from agent_base_core.errors import RunNotFound, ThreadBusy, UnknownRoute
from agent_base_core.ports.checkpointer import CheckpointerFactory
from agent_base_core.ports.event_sink import EventSink
from agent_base_core.ports.graph_runtime import GraphRuntime
from agent_base_core.ports.hooks import RunHooks
from agent_base_core.ports.run_control import RunCancelRegistry
from agent_base_core.ports.thread_lock import ThreadLock
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
    ) -> None:
        self._locks = locks
        self._checkpointers = checkpointers
        self._graphs = graphs
        self._tools = tools
        self._input_builders = input_builders
        self._runtime = runtime
        self._cancels = cancels
        self._hooks = hooks

    def replace_runtime(self, runtime: GraphRuntime) -> None:
        """Test/host hook to swap GraphRuntime without private attribute access."""
        self._runtime = runtime

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

    async def start_stream(
        self,
        *,
        query: str,
        thread_id: str,
        route: str,
        sink: EventSink,
        model: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        run_id = f"r-{uuid.uuid4().hex[:12]}"
        trace_id = run_id
        sequence = 0
        terminal_sent = False

        if not await self._locks.try_acquire(thread_id, run_id):
            raise ThreadBusy(thread_id)

        cancel_token = asyncio.Event()
        cancelled = False
        # Register immediately so /cancel works before start is emitted.
        await self._cancels.register(thread_id, run_id, cancel_token)
        try:
            builder = self._graphs.get(route)
            try:
                tools = self._tools.get(route)
            except UnknownRoute:
                tools = []
            try:
                input_builder = self._input_builders.get(route)
                graph_input = input_builder(query, model=model, extra=extra or {})
            except UnknownRoute:
                graph_input = {"messages": [query]}

            sequence += 1
            await sink.emit(
                build_event(
                    "start",
                    run_id=run_id,
                    sequence=sequence,
                    trace_id=trace_id,
                    data={"thread_id": thread_id, "route": route},
                )
            )

            checkpointer = await self._checkpointers.get()

            try:
                async for frag in self._runtime.astream(
                    builder,
                    tools=tools,
                    checkpointer=checkpointer,
                    thread_id=thread_id,
                    query=query,
                    cancel_token=cancel_token,
                    extra={
                        **(extra or {}),
                        "run_id": run_id,
                        "trace_id": trace_id,
                        "graph_input": graph_input,
                        "model": model,
                    },
                ):
                    if cancel_token.is_set():
                        cancelled = True
                        break
                    if not isinstance(frag, OutboundFragment):
                        raise TypeError(
                            f"runtime must yield OutboundFragment, got {type(frag)!r}"
                        )
                    try:
                        evt = self._envelope_from_fragment(
                            frag, run_id=run_id, sequence=sequence + 1, trace_id=trace_id
                        )
                    except ValueError:
                        sequence += 1
                        await sink.emit(
                            build_event(
                                "error",
                                run_id=run_id,
                                sequence=sequence,
                                trace_id=trace_id,
                                data={
                                    "message": f"invalid event type: {frag.type}",
                                    "code": "invalid_event_type",
                                },
                            )
                        )
                        terminal_sent = True
                        return
                    sequence += 1
                    await sink.emit(evt)
            except Exception as exc:  # noqa: BLE001 — map to SSE error then close
                logger.exception("run failed thread_id=%s run_id=%s", thread_id, run_id)
                sequence += 1
                await sink.emit(
                    build_event(
                        "error",
                        run_id=run_id,
                        sequence=sequence,
                        trace_id=trace_id,
                        data={"message": str(exc), "code": "run_failed"},
                    )
                )
                terminal_sent = True
                return

            if cancel_token.is_set():
                cancelled = True

            if cancelled:
                sequence += 1
                await sink.emit(
                    build_event(
                        "cancel_requested",
                        run_id=run_id,
                        sequence=sequence,
                        trace_id=trace_id,
                        data={"thread_id": thread_id, "run_id": run_id},
                    )
                )
                sequence += 1
                await sink.emit(
                    build_event(
                        "cancelled",
                        run_id=run_id,
                        sequence=sequence,
                        trace_id=trace_id,
                        data={"thread_id": thread_id, "run_id": run_id},
                    )
                )
                terminal_sent = True
            else:
                sequence += 1
                await sink.emit(
                    build_event(
                        "done",
                        run_id=run_id,
                        sequence=sequence,
                        trace_id=trace_id,
                    )
                )
                terminal_sent = True
        except Exception as exc:  # noqa: BLE001
            if not terminal_sent and sequence > 0:
                logger.exception(
                    "run failed after start thread_id=%s run_id=%s", thread_id, run_id
                )
                sequence += 1
                await sink.emit(
                    build_event(
                        "error",
                        run_id=run_id,
                        sequence=sequence,
                        trace_id=trace_id,
                        data={"message": str(exc), "code": "run_failed"},
                    )
                )
                terminal_sent = True
            else:
                raise
        finally:
            await self._hooks.on_run_end(
                {"thread_id": thread_id, "run_id": run_id, "route": route}
            )
            await self._locks.release(thread_id, run_id)
            await self._cancels.unregister(thread_id, run_id)
            await sink.close()

    async def cancel(self, *, thread_id: str, run_id: str | None = None) -> None:
        ok = await self._cancels.request_cancel(thread_id, run_id)
        if not ok:
            raise RunNotFound(thread_id)
