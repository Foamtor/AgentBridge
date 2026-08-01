"""Build KnowledgeIngest from Settings (lifespan-only)."""

from __future__ import annotations

from typing import Any

from agentbridge_core.adapters.memory_ingest_job_store import MemoryIngestJobStore
from agentbridge_core.adapters.retriever_knowledge_ingest import (
    RetrieverKnowledgeIngest,
)
from agentbridge_core.adapters.unsupported_knowledge_ingest import (
    UnsupportedKnowledgeIngest,
)
from config.settings import Settings


def build_knowledge_ingest(
    settings: Settings,
    retriever: Any,
    job_store: MemoryIngestJobStore,
) -> RetrieverKnowledgeIngest | UnsupportedKnowledgeIngest:
    backend = (settings.knowledge_backend or "fake").strip().lower()
    if backend in {"fake", "langchain_pg"}:
        return RetrieverKnowledgeIngest(retriever, job_store)
    if backend == "rag_agent_pg":
        return UnsupportedKnowledgeIngest("rag_agent_pg")
    return UnsupportedKnowledgeIngest(backend)
