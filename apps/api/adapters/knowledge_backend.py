"""Build Retriever from Settings (composition helper; lifespan-only)."""

from __future__ import annotations

from typing import Any

from agentbridge_core.adapters.fake_retriever import FakeRetriever
from config.settings import Settings

_RAG_AGENT_EMBED_MODEL = "BAAI/bge-m3"
_RAG_AGENT_EMBED_DIMENSIONS = 512
_WORK_ORDER_REFERENCE_DOCS = [
    {
        "chunk_id": "work-order-reference-sop",
        "doc_id": "work-order-reference-sop",
        "text": (
            "工单处理 SOP : 确认影响范围和优先级，分配有效处理人，"
            "记录台账摘要，再提交草稿等待人工审批后创建工单。 "
            "Work-order handling SOP: confirm impact and priority, assign an "
            "active owner, record the ledger summary, then submit the draft "
            "for human approval before creation."
        ),
        "metadata": {"source": "bundled-reference", "synthetic": True},
    }
]


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


def validate_rag_agent_pg_settings(settings: Settings) -> None:
    missing: list[str] = []
    incompatible: list[str] = []
    if not (settings.rag_agent_pg_dsn or "").strip():
        missing.append("RAG_AGENT_PG_DSN")
    if not (settings.rag_agent_demo_tenant or "").strip():
        missing.append("RAG_AGENT_DEMO_TENANT")
    if not (settings.rag_agent_embed_api_base or "").strip():
        missing.append("RAG_AGENT_EMBED_API_BASE")
    model = (settings.rag_agent_embed_model or "").strip()
    if not model:
        missing.append("RAG_AGENT_EMBED_MODEL")
    elif model != _RAG_AGENT_EMBED_MODEL:
        incompatible.append(
            f"RAG_AGENT_EMBED_MODEL must be {_RAG_AGENT_EMBED_MODEL}"
        )
    dimensions = settings.rag_agent_embed_dimensions
    if dimensions is None or int(dimensions) <= 0:
        missing.append("RAG_AGENT_EMBED_DIMENSIONS")
    elif int(dimensions) != _RAG_AGENT_EMBED_DIMENSIONS:
        incompatible.append(
            f"RAG_AGENT_EMBED_DIMENSIONS must be {_RAG_AGENT_EMBED_DIMENSIONS}"
        )
    if missing:
        raise RuntimeError(
            "KNOWLEDGE_BACKEND=rag_agent_pg missing required config: "
            + ", ".join(missing)
        )
    if incompatible:
        raise RuntimeError(
            "KNOWLEDGE_BACKEND=rag_agent_pg incompatible config: "
            + ", ".join(incompatible)
        )


async def build_retriever(settings: Settings) -> Any:
    backend = (settings.knowledge_backend or "fake").strip().lower()
    if backend == "fake":
        retriever = FakeRetriever()
        await retriever.ingest(_WORK_ORDER_REFERENCE_DOCS, tenant_id="dev")
        return retriever
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
        from agentbridge_core.adapters.langchain_pg_retriever import (
            LangchainPgRetriever,
        )

        return await LangchainPgRetriever.create(
            dsn=resolve_kb_dsn(settings),
            embed_api_base=settings.embed_api_base,
            embed_model=settings.embed_model,
            embed_dimensions=int(settings.embed_dimensions),
            embed_api_key=settings.embed_api_key or "",
        )
    if backend == "rag_agent_pg":
        validate_rag_agent_pg_settings(settings)
        from adapters.rag_agent_pg_retriever import RagAgentPgRetriever

        return await RagAgentPgRetriever.create(
            dsn=settings.rag_agent_pg_dsn.strip(),
            demo_tenant=settings.rag_agent_demo_tenant.strip(),
            embed_api_base=settings.rag_agent_embed_api_base.strip(),
            embed_api_key=settings.rag_agent_embed_api_key or "",
            embed_model=settings.rag_agent_embed_model.strip(),
            embed_dimensions=int(settings.rag_agent_embed_dimensions),
        )
    raise RuntimeError(
        "Unsupported KNOWLEDGE_BACKEND="
        f"{backend!r}; use fake|langchain_pg|external|rag_agent_pg"
    )
