"""Composition root: wire adapters into RunLifecycle + domain bootstrap."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from adapters.domain_prompt_registry import DomainFilePromptRegistry
from adapters.knowledge_ingest_factory import build_knowledge_ingest
from adapters.knowledge_status import build_knowledge_status_provider
from adapters.memory_usage_store import MemoryUsageStore
from admin.catalog import build_domain_catalog
from agentbridge_core.adapters.basic_input_validator import BasicInputValidator
from agentbridge_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agentbridge_core.adapters.inprocess_lock import InProcessThreadLock
from agentbridge_core.adapters.langgraph_runtime import LangGraphRuntime
from agentbridge_core.adapters.layered_prompt_registry import LayeredPromptRegistry
from agentbridge_core.adapters.logging_hooks import LoggingHooks
from agentbridge_core.adapters.memory_approval_store import MemoryApprovalStore
from agentbridge_core.adapters.memory_audit_logger import MemoryAuditLogger
from agentbridge_core.adapters.memory_checkpointer import MemoryCheckpointerFactory
from agentbridge_core.adapters.memory_config_provider import MemoryConfigProvider
from agentbridge_core.adapters.memory_event_log import MemoryEventLog
from agentbridge_core.adapters.memory_ingest_job_store import MemoryIngestJobStore
from agentbridge_core.adapters.memory_message_store import MemoryMessageStore
from agentbridge_core.adapters.memory_prompt_registry import MemoryPromptRegistry
from agentbridge_core.adapters.memory_run_store import MemoryRunStore
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
from domains.bootstrap import DOMAIN_META_MAP, register_all
from fastapi import FastAPI

logger = logging.getLogger(__name__)


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


def _build_console_auth_store(settings: Settings) -> Any:
    if settings.resolved_auth_mode != "local":
        return None
    if settings.fake_runtime:
        from testing.fake_console_auth import FakeConsoleAuthStore

        return FakeConsoleAuthStore()
    from adapters.postgres_console_auth import PostgresConsoleAuthStore

    return PostgresConsoleAuthStore(_resolve_postgres_dsn(settings))


def _build_observability_stores(settings: Settings) -> tuple[Any, Any, Any, Any]:
    """Build durable run evidence stores at the application composition root."""
    if settings.observability_store_backend == "memory":
        from observability.annotation_store import MemoryRunAnnotationStore

        return (
            MemoryEventLog(),
            MemoryMessageStore(),
            MemoryRunStore(),
            MemoryRunAnnotationStore(),
        )
    if settings.observability_store_backend == "postgres":
        from adapters.postgres_observability_store import (
            PostgresEventLog,
            PostgresMessageStore,
            PostgresRunAnnotationStore,
            PostgresRunStore,
        )

        dsn = _resolve_postgres_dsn(settings)
        return (
            PostgresEventLog(dsn),
            PostgresMessageStore(dsn),
            PostgresRunStore(dsn),
            PostgresRunAnnotationStore(dsn),
        )
    raise ValueError("unsupported observability store backend")


def _build_llm_models(settings: Settings) -> tuple[dict[str, Any], set[str]]:
    """Build host-owned fallback models; persistent aliases are overlaid later."""
    from agentbridge_core.adapters.alias_llm_gateway import AliasLLMGateway
    from agentbridge_core.adapters.fake_chat_model import FakeChatModel

    if settings.llm_mode == "openai_compatible":
        if not settings.llm_api_key.strip():
            raise ValueError(
                "LLM_MODE=openai_compatible requires LLM_API_KEY"
            )
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - packaging failure
            raise RuntimeError(
                "LLM_MODE=openai_compatible requires agentbridge-core[rag]"
            ) from exc
        default_model = ChatOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_base.rstrip("/"),
            model=settings.llm_model,
            temperature=settings.llm_temperature,
        )
    elif settings.llm_mode == "fake":
        default_model = FakeChatModel(["direct-ok"])
    else:
        raise ValueError("unsupported LLM_MODE; use fake or openai_compatible")
    models = {"default": default_model, "fast": default_model}
    return models, ({"default", "fast"} if settings.llm_mode == "openai_compatible" else set())


def _build_llm_gateway(settings: Settings) -> tuple[Any, dict[str, Any], set[str]]:
    """Always expose aliases so operator-managed models can be selected safely."""
    from agentbridge_core.adapters.alias_llm_gateway import AliasLLMGateway

    models, real_aliases = _build_llm_models(settings)
    return AliasLLMGateway(models, default_alias="default"), models, real_aliases


def _build_model_config_store(settings: Settings) -> Any:
    if settings.fake_runtime:
        from testing.fake_model_config import FakeModelConfigStore

        return FakeModelConfigStore()
    if not settings.model_config_encryption_key.strip():
        from adapters.unavailable_model_config_store import UnavailableModelConfigStore

        return UnavailableModelConfigStore()
    from adapters.postgres_model_config_store import PostgresModelConfigStore

    return PostgresModelConfigStore(_resolve_postgres_dsn(settings))


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
    event_log, message_store, run_store, run_annotation_store = (
        _build_observability_stores(settings)
    )
    config_provider = MemoryConfigProvider()
    platform_prompt_registry = MemoryPromptRegistry()
    prompt_runtime = LayeredPromptRegistry(
        platform_prompt_registry,
        DomainFilePromptRegistry(Path(__file__).resolve().parent / "domains"),
    )
    usage_store = MemoryUsageStore()
    approval_store = _build_approval_store(settings)
    console_auth_store = _build_console_auth_store(settings)
    console_auth_service: Any | None = None
    model_config_store = _build_model_config_store(settings)
    model_config_service: Any | None = None
    from adapters.approval_action_registry import ApprovalActionRegistry

    approval_actions = ApprovalActionRegistry()
    from adapters.knowledge_backend import build_retriever

    retriever = await build_retriever(settings)
    data_source: Any | None = None
    approval_expiry_task: asyncio.Task[Any] | None = None
    try:
        ingest_job_store = MemoryIngestJobStore()
        knowledge_ingest = build_knowledge_ingest(
            settings,
            retriever,
            ingest_job_store,
        )
        knowledge_status_provider = build_knowledge_status_provider(
            settings,
            retriever,
            ingest_jobs=ingest_job_store,
        )
        data_source = (
            getattr(app.state, "bootstrap_data_source", None)
            or _build_data_source(settings)
        )
        if console_auth_store is not None:
            from auth.local_admin import ConsoleAdminService

            console_auth_service = ConsoleAdminService(
                console_auth_store,
                session_idle_seconds=settings.auth_session_idle_seconds,
                session_absolute_seconds=settings.auth_session_absolute_seconds,
                password_change_seconds=settings.auth_password_change_seconds,
                    password_min_length=settings.auth_password_min_length,
                    password_max_length=settings.auth_password_max_length,
                    login_failure_window_seconds=settings.auth_login_failure_window_seconds,
                    initial_password_ttl_seconds=settings.auth_initial_password_ttl_seconds,
                )
            bootstrap = await console_auth_service.ensure_admin()
            if bootstrap is not None:
                logger.warning(
                    "AGENTBRIDGE_INITIAL_ADMIN_PASSWORD username=%s password=%s",
                    bootstrap.username,
                    bootstrap.initial_password,
                )
        register_all(
            graphs,
            tools,
            input_builders,
            approval_actions=approval_actions,
            data_source=data_source,
        )
        llm_gateway, base_models, base_real_aliases = _build_llm_gateway(settings)
        from admin.model_config_service import ModelConfigService

        def build_configured_model(record: dict[str, Any], api_key: str) -> Any:
            try:
                from langchain_openai import ChatOpenAI
            except ImportError as exc:  # pragma: no cover - packaging failure
                raise RuntimeError(
                    "configured models require agentbridge-core[rag]"
                ) from exc
            return ChatOpenAI(
                api_key=api_key,
                base_url=str(record["api_base"]).rstrip("/"),
                model=str(record["model_name"]),
                temperature=float(record["temperature"]),
            )

        await model_config_store.setup()
        model_config_service = ModelConfigService(
            model_config_store,
            encryption_key=settings.model_config_encryption_key,
            build_model=build_configured_model,
            replace_gateway_models=llm_gateway.replace_models,
            base_models=base_models,
            base_real_aliases=base_real_aliases,
        )
        await model_config_service.refresh_runtime()
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
            approval_execution_lease_seconds=(
                settings.approval_execution_lease_seconds
            ),
            safety_hooks=SafetyHooks(redact=True),
        )

        async def _approval_expiry_loop() -> None:
            await lifecycle.expire_pending_approvals(
                now=datetime.now(timezone.utc)
            )

            while True:
                await asyncio.sleep(
                    settings.approval_expiry_scan_interval_seconds
                )
                await lifecycle.expire_pending_approvals(
                    now=datetime.now(timezone.utc)
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
        app.state.run_annotation_store = run_annotation_store
        app.state.approval_store = approval_store
        app.state.console_auth_service = console_auth_service
        app.state.model_config_service = model_config_service
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
        approval_expiry_task = asyncio.create_task(_approval_expiry_loop())
        yield
    finally:
        try:
            if approval_expiry_task is not None:
                approval_expiry_task.cancel()
                with suppress(asyncio.CancelledError):
                    await approval_expiry_task
        finally:
            close_retriever = getattr(retriever, "close", None)
            if close_retriever is not None:
                result = close_retriever()
                if hasattr(result, "__await__"):
                    await result
            if data_source is not None:
                await data_source.close()
            close_approval_store = getattr(approval_store, "close", None)
            if close_approval_store is not None:
                result = close_approval_store()
                if hasattr(result, "__await__"):
                    await result
            if console_auth_store is not None:
                close_console_auth_store = getattr(console_auth_store, "close", None)
                if close_console_auth_store is not None:
                    result = close_console_auth_store()
                    if hasattr(result, "__await__"):
                        await result
            close_model_config_store = getattr(model_config_store, "close", None)
            if close_model_config_store is not None:
                result = close_model_config_store()
                if hasattr(result, "__await__"):
                    await result
            for store in (
                event_log,
                message_store,
                run_store,
                run_annotation_store,
            ):
                close_store = getattr(store, "close", None)
                if close_store is not None:
                    result = close_store()
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
