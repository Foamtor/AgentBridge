"""Build Retriever from Settings (composition helper; lifespan-only)."""

from __future__ import annotations

from typing import Any

from agent_base_core.adapters.fake_retriever import FakeRetriever
from config.settings import Settings


def resolve_kb_dsn(settings: Settings) -> str:
    if settings.kb_dsn:
        return settings.kb_dsn
    if settings.pg_dsn:
        return settings.pg_dsn
    return (
        f"postgresql://{settings.pg_user}:{settings.pg_password}"
        f"@{settings.pg_host}:{settings.pg_port}/{settings.pg_database}"
    )


def validate_langchain_pg_settings(settings: Settings) -> None:
    missing: list[str] = []
    if not (settings.embed_api_base or "").strip():
        missing.append("EMBED_API_BASE")
    if not (settings.embed_model or "").strip():
        missing.append("EMBED_MODEL")
    if settings.embed_dimensions is None or int(settings.embed_dimensions) <= 0:
        missing.append("EMBED_DIMENSIONS")
    dsn = resolve_kb_dsn(settings)
    if not dsn.strip():
        missing.append("KB_DSN or PG_DSN")
    if missing:
        raise RuntimeError(
            "KNOWLEDGE_BACKEND=langchain_pg missing required config: "
            + ", ".join(missing)
        )


def validate_external_settings(settings: Settings) -> None:
    if not (settings.kb_external_base_url or "").strip():
        raise RuntimeError(
            "KNOWLEDGE_BACKEND=external missing required config: KB_EXTERNAL_BASE_URL"
        )


async def build_retriever(settings: Settings) -> Any:
    backend = (settings.knowledge_backend or "fake").strip().lower()
    if backend == "fake":
        return FakeRetriever()
    if backend == "external":
        validate_external_settings(settings)
        from adapters.external_rag_retriever import ExternalRagRetriever

        return ExternalRagRetriever(
            base_url=settings.kb_external_base_url.strip(),
            api_key=settings.kb_external_api_key or "",
            timeout_seconds=float(settings.kb_external_timeout_seconds),
            failure_policy=settings.kb_external_failure_policy,
        )
    if backend == "langchain_pg":
        validate_langchain_pg_settings(settings)
        from agent_base_core.adapters.langchain_pg_retriever import LangchainPgRetriever

        return await LangchainPgRetriever.create(
            dsn=resolve_kb_dsn(settings),
            embed_api_base=settings.embed_api_base,
            embed_model=settings.embed_model,
            embed_dimensions=int(settings.embed_dimensions),
            embed_api_key=settings.embed_api_key or "",
        )
    raise RuntimeError(
        f"Unsupported KNOWLEDGE_BACKEND={backend!r}; use fake|langchain_pg|external"
    )
