"""RunLifecycle: lock -> run graph -> emit events -> release."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from agent_base_core.application.errors import RunNotFound, ThreadBusy, UnknownRoute
from agent_base_core.ports.checkpointer import CheckpointerFactory
from agent_base_core.ports.event_sink import EventSink
from agent_base_core.ports.graph_runtime import GraphRuntime
from agent_base_core.ports.hooks import RunHooks
from agent_base_core.ports.run_control import RunCancelRegistry
from agent_base_core.ports.thread_lock import ThreadLock
from agent_base_core.protocol.events import build_event
from agent_base_core.registry.graphs import GraphRegistry
from agent_base_core.registry.input_builders import InputBuilderRegistry
from agent_base_core.registry.tools import ToolRegistry


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

        if not await self._locks.try_acquire(thread_id, run_id):
            raise ThreadBusy(thread_id)

        cancel_token = asyncio.Event()
        cancelled = False
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

            await self._cancels.register(thread_id, run_id, cancel_token)
            checkpointer = await self._checkpointers.get()

            async for evt in self._runtime.astream(
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
                await sink.emit(evt)

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
                    )
                )
                sequence += 1
                await sink.emit(
                    build_event(
                        "cancelled",
                        run_id=run_id,
                        sequence=sequence,
                        trace_id=trace_id,
                    )
                )
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
