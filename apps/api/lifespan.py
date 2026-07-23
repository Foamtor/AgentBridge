"""Composition root: wire adapters into RunLifecycle + domain bootstrap."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI

from agent_base_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agent_base_core.adapters.inprocess_lock import InProcessThreadLock
from agent_base_core.adapters.langgraph_runtime import LangGraphRuntime
from agent_base_core.adapters.memory_checkpointer import MemoryCheckpointerFactory
from agent_base_core.adapters.noop_hooks import NoopHooks
from agent_base_core.application.run_lifecycle import RunLifecycle
from agent_base_core.protocol.events import build_event
from agent_base_core.registry.graphs import GraphRegistry
from agent_base_core.registry.input_builders import InputBuilderRegistry
from agent_base_core.registry.tools import ToolRegistry
from config.logging import configure_logging
from config.settings import get_settings
from domains.bootstrap import register_all


class ApiFakeRuntime:
    """Deterministic runtime for API tests (AGENT_BASE_FAKE_RUNTIME=1)."""

    async def astream(self, builder: Any, **kwargs: Any):
        extra = kwargs.get("extra") or {}
        run_id = str(extra.get("run_id") or "r-x")
        trace_id = str(extra.get("trace_id") or run_id)
        yield build_event(
            "text_delta",
            run_id=run_id,
            sequence=2,
            trace_id=trace_id,
            data={"content": "ok"},
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()

    locks = InProcessThreadLock()
    cancels = InProcessCancelRegistry()
    graphs = GraphRegistry()
    tools = ToolRegistry()
    input_builders = InputBuilderRegistry()
    register_all(graphs, tools, input_builders)

    checkpointers = MemoryCheckpointerFactory()
    await checkpointers.setup()

    runtime: Any = ApiFakeRuntime() if settings.fake_runtime else LangGraphRuntime()
    lifecycle = RunLifecycle(
        locks=locks,
        checkpointers=checkpointers,
        graphs=graphs,
        tools=tools,
        input_builders=input_builders,
        runtime=runtime,
        cancels=cancels,
        hooks=NoopHooks(),
    )

    app.state.settings = settings
    app.state.run_lifecycle = lifecycle
    app.state.graphs = graphs
    app.state.tools = tools
    app.state.input_builders = input_builders
    try:
        yield
    finally:
        await checkpointers.teardown()
