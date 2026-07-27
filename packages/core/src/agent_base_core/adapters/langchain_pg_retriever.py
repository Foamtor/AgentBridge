"""PGVector retriever via langchain-postgres (optional rag extra)."""

from __future__ import annotations

import logging
from typing import Any

from agent_base_core.protocol.knowledge import (
    KnowledgeHit,
    doc_to_knowledge_hit,
    normalize_ingest_doc,
    require_tenant_id,
)

logger = logging.getLogger(__name__)


class LangchainPgRetriever:
    """Retriever backed by a LangChain vector store.

    Production: use ``create(...)`` (lazy-imports rag extra).
    Tests: inject ``store`` with ``aadd_documents`` / ``asimilarity_search_with_score``.
    """

    def __init__(
        self,
        *,
        store: Any,
        embeddings: Any | None = None,
        engine: Any | None = None,
    ) -> None:
        self._store = store
        self._embeddings = embeddings
        self._engine = engine

    @classmethod
    async def create(
        cls,
        *,
        dsn: str,
        embed_api_base: str,
        embed_model: str,
        embed_dimensions: int,
        embed_api_key: str = "",
        schema_name: str = "knowledge",
        table_name: str = "kb_chunks",
    ) -> LangchainPgRetriever:
        try:
            from langchain_openai import OpenAIEmbeddings
            from langchain_postgres import PGEngine, PGVectorStore
            from langchain_postgres.v2.indexes import DistanceStrategy
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "KNOWLEDGE_BACKEND=langchain_pg requires optional extra 'rag' "
                '(pip install -e "packages/core[rag]" or apps/api[rag])'
            ) from exc

        embeddings = OpenAIEmbeddings(
            model=embed_model,
            api_key=embed_api_key or "not-needed",
            base_url=embed_api_base.rstrip("/"),
            dimensions=embed_dimensions,
        )
        engine = PGEngine.from_connection_string(url=dsn)
        # Table must already exist (migration 003). Do NOT init_vectorstore_table.
        store = await PGVectorStore.create(
            engine=engine,
            table_name=table_name,
            schema_name=schema_name,
            embedding_service=embeddings,
            metadata_columns=["tenant_id", "chunk_id", "doc_id"],
            distance_strategy=DistanceStrategy.COSINE_DISTANCE,
        )
        return cls(store=store, embeddings=embeddings, engine=engine)

    async def close(self) -> None:
        engine = self._engine
        if engine is None:
            return
        close = getattr(engine, "close", None) or getattr(engine, "aclose", None)
        if close is None:
            return
        result = close()
        if hasattr(result, "__await__"):
            await result

    async def ingest(self, docs: list[dict[str, Any]], *, tenant_id: str) -> int:
        from langchain_core.documents import Document

        tid = require_tenant_id(tenant_id)
        normalized = [normalize_ingest_doc(d, tenant_id=tid) for d in docs]
        documents = [
            Document(
                page_content=n["text"],
                metadata={
                    "tenant_id": tid,
                    "chunk_id": n["chunk_id"],
                    "doc_id": n["doc_id"],
                    **(n.get("metadata") or {}),
                },
            )
            for n in normalized
        ]
        await self._store.aadd_documents(documents)
        return len(documents)

    async def similarity_search(
        self, query: str, *, tenant_id: str, k: int = 5
    ) -> list[KnowledgeHit]:
        tid = require_tenant_id(tenant_id)
        try:
            pairs = await self._store.asimilarity_search_with_score(
                query, k=k, filter={"tenant_id": tid}
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "langchain_pg similarity_search failed; returning empty hits",
                exc_info=True,
            )
            return []
        out: list[KnowledgeHit] = []
        for doc, score in pairs:
            meta = dict(getattr(doc, "metadata", None) or {})
            raw = {
                "chunk_id": meta.get("chunk_id") or meta.get("id") or "",
                "doc_id": meta.get("doc_id") or meta.get("chunk_id") or "",
                "text": getattr(doc, "page_content", "") or "",
                "tenant_id": meta.get("tenant_id") or tid,
                "metadata": meta,
            }
            if not raw["chunk_id"]:
                continue
            try:
                hit = doc_to_knowledge_hit(raw, tenant_id=tid, score=float(score))
            except ValueError:
                continue
            if hit["tenant_id"] != tid:
                continue
            out.append(hit)
        return out
