"""Composition root: wire adapters into RunLifecycle + domain bootstrap."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI

from agentbridge_core.adapters.basic_input_validator import BasicInputValidator
from agentbridge_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agentbridge_core.adapters.inprocess_lock import InProcessThreadLock
from agentbridge_core.adapters.langgraph_runtime import LangGraphRuntime
from agentbridge_core.adapters.logging_hooks import LoggingHooks
from agentbridge_core.adapters.memory_approval_store import MemoryApprovalStore
from agentbridge_core.adapters.memory_audit_logger import MemoryAuditLogger
from agentbridge_core.adapters.memory_checkpointer import MemoryCheckpointerFactory
from agentbridge_core.adapters.memory_event_log import MemoryEventLog
from agentbridge_core.adapters.memory_message_store import MemoryMessageStore
from agentbridge_core.adapters.memory_run_store import MemoryRunStore
from agentbridge_core.adapters.memory_ingest_job_store import MemoryIngestJobStore
from agentbridge_core.adapters.memory_config_provider import MemoryConfigProvider
from agentbridge_core.adapters.layered_prompt_registry import LayeredPromptRegistry
from agentbridge_core.adapters.memory_prompt_registry import MemoryPromptRegistry
from agentbridge_core.adapters.noop_data_source import NoopDataSource
from agentbridge_core.adapters.noop_hooks import NoopHooks
from agentbridge_core.adapters.role_policy import RolePolicyEngine
from agentbridge_core.adapters.safety_hooks import SafetyHooks
from agentbridge_core.application.pipeline import (
    InputValidatorPlugin,
    RequestPipeline,
    ToolPolicyPlugin,
)
from agentbridge_core.application.run_lifecycle import RunLifecycle
from agentbridge_core.registry.graphs import GraphRegistry
from agentbridge_core.registry.input_builders import InputBuilderRegistry
from agentbridge_core.registry.tools import ToolRegistry
from config.logging import configure_logging
from config.settings import Settings, get_settings
from admin.catalog import build_domain_catalog
from adapters.domain_prompt_registry import DomainFilePromptRegistry
from adapters.knowledge_ingest_factory import build_knowledge_ingest
from adapters.knowledge_status import build_knowledge_status_provider
from adapters.memory_usage_store import MemoryUsageStore
from domains.bootstrap import DOMAIN_META_MAP, register_all


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


def _build_approval_store(settings: Settings) -> Any:
    if settings.approval_store_backend == "memory":
        return MemoryApprovalStore()
    if settings.approval_store_backend == "postgres":
        from adapters.postgres_approval_store import PostgresApprovalStore

        return PostgresApprovalStore(_resolve_postgres_dsn(settings))
    raise ValueError("unsupported approval store backend")


def _build_llm_gateway(settings: Settings) -> Any:
    """Build gateway; default FakeChatModel keeps CI offline."""
    from agentbridge_core.adapters.alias_llm_gateway import AliasLLMGateway
    from agentbridge_core.adapters.direct_llm_gateway import DirectLLMGateway
    from agentbridge_core.adapters.fake_chat_model import FakeChatModel

    default_model = FakeChatModel(["direct-ok"])
    if settings.llm_backend == "gateway":
        # Aliases are host-wired; domains only pass model= alias strings.
        return AliasLLMGateway(
            {
                "default": FakeChatModel(["gateway-default"]),
                "fast": FakeChatModel(["gateway-fast"]),
            },
            default_alias="default",
        )
    return DirectLLMGateway(default_model)


def _build_redis(settings: Settings) -> Any | None:
    if settings.lock_backend != "redis" and settings.rate_limit_backend != "redis":
        return None
    import redis.asyncio as redis

    return redis.from_url(settings.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()

    redis_client = getattr(app.state, "bootstrap_redis", None)
    locks: Any
    if settings.lock_backend == "redis":
        if redis_client is None:
            redis_client = _build_redis(settings)
        from adapters.redis_thread_lock import RedisThreadLock

        locks = RedisThreadLock(redis_client)
    else:
        locks = InProcessThreadLock()
    cancels = InProcessCancelRegistry()
    graphs = GraphRegistry()
    tools = ToolRegistry()
    input_builders = InputBuilderRegistry()

    checkpointers: Any
    if settings.use_memory_checkpointer:
        checkpointers = MemoryCheckpointerFactory()
    else:
        from agentbridge_core.adapters.postgres_checkpointer import (
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
    config_provider = MemoryConfigProvider()
    platform_prompt_registry = MemoryPromptRegistry()
    prompt_runtime = LayeredPromptRegistry(
        platform_prompt_registry,
        DomainFilePromptRegistry(Path(__file__).resolve().parent / "domains"),
    )
    usage_store = MemoryUsageStore()
    approval_store = _build_approval_store(settings)
    from adapters.approval_action_registry import ApprovalActionRegistry

    approval_actions = ApprovalActionRegistry()
    from adapters.knowledge_backend import build_retriever

    retriever = await build_retriever(settings)
    ingest_job_store = MemoryIngestJobStore()
    knowledge_ingest = build_knowledge_ingest(settings, retriever, ingest_job_store)
    knowledge_status_provider = build_knowledge_status_provider(
        settings,
        retriever,
        ingest_jobs=ingest_job_store,
    )
    data_source = getattr(app.state, "bootstrap_data_source", None) or _build_data_source(settings)
    register_all(graphs, tools, input_builders, approval_actions=approval_actions, data_source=data_source)
    llm_gateway = _build_llm_gateway(settings)
    from adapters.prometheus_metrics import PrometheusMetrics
    from observability.tracing import make_run_span_factory

    metrics = PrometheusMetrics()
    span_factory = make_run_span_factory(enabled=settings.otel_enabled)

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
        span_factory=span_factory,
        approval_store=approval_store,
        approval_executor=approval_actions,
        approval_execution_lease_seconds=settings.approval_execution_lease_seconds,
        safety_hooks=SafetyHooks(redact=True),
    )
    pipeline = RequestPipeline(
        lifecycle=lifecycle,
        plugins=[
            InputValidatorPlugin(BasicInputValidator()),
            ToolPolicyPlugin(
                policy=policy,
                audit=audit,
                tools_registry=tools,
            ),
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
    app.state.approval_store = approval_store
    app.state.approval_actions = approval_actions
    app.state.policy = policy
    app.state.config_provider = config_provider
    app.state.prompt_registry = platform_prompt_registry
    app.state.prompt_runtime = prompt_runtime
    app.state.usage_store = usage_store
    app.state.retriever = retriever
    app.state.ingest_job_store = ingest_job_store
    app.state.knowledge_ingest = knowledge_ingest
    app.state.knowledge_status_provider = knowledge_status_provider
    app.state.data_source = data_source
    app.state.llm_gateway = llm_gateway
    app.state.metrics = metrics
    app.state.tools = tools
    app.state.graphs = graphs
    app.state.domain_catalog = build_domain_catalog(
        route_names=tools.keys(),
        tools_registry=tools,
        graph_names=set(graphs.keys()),
        meta_map=DOMAIN_META_MAP,
    )
    # Expose checkpointer factory for /ready (memory always "ready" after setup).
    app.state.checkpointers = checkpointers
    app.state.redis = redis_client
    try:
        yield
    finally:
        close_retriever = getattr(retriever, "close", None)
        if close_retriever is not None:
            result = close_retriever()
            if hasattr(result, "__await__"):
                await result
        await data_source.close()
        close_approval_store = getattr(approval_store, "close", None)
        if close_approval_store is not None:
            result = close_approval_store()
            if hasattr(result, "__await__"):
                await result
        await checkpointers.teardown()
        if redis_client is not None:
            close = getattr(redis_client, "aclose", None) or getattr(
                redis_client, "close", None
            )
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result
