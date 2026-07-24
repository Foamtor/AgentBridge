"""Composition root: wire adapters into RunLifecycle + domain bootstrap."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI

from agent_base_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agent_base_core.adapters.inprocess_lock import InProcessThreadLock
from agent_base_core.adapters.langgraph_runtime import LangGraphRuntime
from agent_base_core.adapters.logging_hooks import LoggingHooks
from agent_base_core.adapters.memory_audit_logger import MemoryAuditLogger
from agent_base_core.adapters.memory_checkpointer import MemoryCheckpointerFactory
from agent_base_core.adapters.memory_event_log import MemoryEventLog
from agent_base_core.adapters.memory_message_store import MemoryMessageStore
from agent_base_core.adapters.memory_run_store import MemoryRunStore
from agent_base_core.adapters.noop_data_source import NoopDataSource
from agent_base_core.adapters.noop_hooks import NoopHooks
from agent_base_core.adapters.role_policy import RolePolicyEngine
from agent_base_core.application.pipeline import RequestPipeline, ToolPolicyPlugin
from agent_base_core.application.run_lifecycle import RunLifecycle
from agent_base_core.registry.graphs import GraphRegistry
from agent_base_core.registry.input_builders import InputBuilderRegistry
from agent_base_core.registry.tools import ToolRegistry
from config.logging import configure_logging
from config.settings import Settings, get_settings
from domains.bootstrap import register_all


def _resolve_postgres_dsn(settings: Settings) -> str:
    if settings.pg_dsn:
        return settings.pg_dsn
    return (
        f"postgresql://{settings.pg_user}:{settings.pg_password}"
        f"@{settings.pg_host}:{settings.pg_port}/{settings.pg_database}"
    )


def _build_data_source(settings: Settings) -> Any:
    if not settings.enable_data_source:
        return NoopDataSource()
    dsn = settings.data_source_dsn or _resolve_postgres_dsn(settings)
    from adapters.postgres_data_source import PostgresDataSource

    return PostgresDataSource(dsn)


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

    checkpointers: Any
    if settings.use_memory_checkpointer:
        checkpointers = MemoryCheckpointerFactory()
    else:
        from agent_base_core.adapters.postgres_checkpointer import (
            PostgresCheckpointerFactory,
        )

        checkpointers = PostgresCheckpointerFactory(_resolve_postgres_dsn(settings))
    await checkpointers.setup()

    if settings.fake_runtime:
        from testing.fake_runtime import ApiFakeRuntime

        runtime: Any = ApiFakeRuntime()
    else:
        runtime = LangGraphRuntime()

    hooks: Any
    if settings.hooks_backend == "logging":
        hooks = LoggingHooks()
    else:
        hooks = NoopHooks()

    policy = RolePolicyEngine()
    audit = MemoryAuditLogger()
    event_log = MemoryEventLog()
    message_store = MemoryMessageStore()
    run_store = MemoryRunStore()
    data_source = _build_data_source(settings)
    from adapters.prometheus_metrics import PrometheusMetrics

    metrics = PrometheusMetrics()

    lifecycle = RunLifecycle(
        locks=locks,
        checkpointers=checkpointers,
        graphs=graphs,
        tools=tools,
        input_builders=input_builders,
        runtime=runtime,
        cancels=cancels,
        hooks=hooks,
        policy=policy,
        audit=audit,
        event_log=event_log,
        message_store=message_store,
        run_store=run_store,
        metrics=metrics,
    )
    pipeline = RequestPipeline(
        lifecycle=lifecycle,
        plugins=[
            ToolPolicyPlugin(
                policy=policy,
                audit=audit,
                tools_registry=tools,
            )
        ],
    )

    # Production app.state whitelist: lifecycle + pipeline + settings + stores.
    app.state.settings = settings
    app.state.run_lifecycle = lifecycle
    app.state.pipeline = pipeline
    app.state.audit = audit
    app.state.event_log = event_log
    app.state.message_store = message_store
    app.state.run_store = run_store
    app.state.data_source = data_source
    app.state.metrics = metrics
    app.state.tools = tools
    # Expose checkpointer factory for /ready (memory always "ready" after setup).
    app.state.checkpointers = checkpointers
    try:
        yield
    finally:
        await data_source.close()
        await checkpointers.teardown()
