"""Read-only Retriever for the RAG-Agent PostgreSQL/pgvector schema."""

from __future__ import annotations

import logging
import math
from typing import Any, NoReturn

import httpx
from agentbridge_core.errors import KnowledgeBackendUnavailable
from agentbridge_core.protocol.knowledge import KnowledgeHit

logger = logging.getLogger(__name__)

_BACKEND = "rag_agent_pg"
_EXPECTED_MODEL = "BAAI/bge-m3"
_EXPECTED_DIMENSIONS = 512
_PUBLIC_ERROR = "knowledge backend unavailable"

_EXTENSION_PROBE_SQL = """
SELECT extversion FROM pg_extension WHERE extname = 'vector'
"""

_TABLES_PROBE_SQL = """
SELECT to_regclass('public.kb_document'),
       to_regclass('public.kb_section'),
       to_regclass('public.kb_chunk')
"""

_EMBEDDING_TYPE_PROBE_SQL = """
SELECT format_type(atttypid, atttypmod)
FROM pg_attribute
WHERE attrelid = 'kb_chunk'::regclass
  AND attname = 'embedding' AND NOT attisdropped
"""

_SIMILARITY_SEARCH_SQL = """
SELECT
    c.chunk_id,
    d.doc_id,
    c.content AS text,
    d.title,
    s.section_id,
    s.heading,
    1 - (c.embedding <=> $1::vector) AS score
FROM kb_document d
JOIN kb_section s ON s.document_id = d.id
JOIN kb_chunk c ON c.section_id = s.id
WHERE d.active_version = TRUE
  AND c.embedding IS NOT NULL
ORDER BY c.embedding <=> $1::vector
LIMIT $2
"""


class _CapabilityFailure(RuntimeError):
    """Safe internal probe/response validation detail."""


def _raise_unavailable(stage: str, exc: Exception) -> NoReturn:
    if isinstance(exc, _CapabilityFailure):
        logger.warning(
            "RAG-Agent knowledge backend unavailable stage=%s detail=%s",
            stage,
            exc,
        )
    else:
        logger.warning(
            "RAG-Agent knowledge backend unavailable stage=%s error_type=%s",
            stage,
            type(exc).__name__,
        )
    raise KnowledgeBackendUnavailable(_PUBLIC_ERROR) from None


class RagAgentPgRetriever:
    """Query the existing RAG-Agent schema without ingest or mutation support."""

    def __init__(
        self,
        *,
        dsn: str,
        demo_tenant: str,
        embed_api_base: str,
        embed_api_key: str,
        embed_model: str,
        embed_dimensions: int,
        pool: Any,
        client: httpx.AsyncClient,
        owns_pool: bool = False,
        owns_client: bool = False,
    ) -> None:
        self._demo_tenant = demo_tenant
        self._embed_api_base = embed_api_base.rstrip("/")
        self._embed_api_key = embed_api_key
        self._embed_model = embed_model
        self._embed_dimensions = int(embed_dimensions)
        self._pool = pool
        self._client = client
        self._owns_pool = owns_pool
        self._owns_client = owns_client
        self._closed = False

    @classmethod
    async def create(
        cls,
        *,
        dsn: str,
        demo_tenant: str,
        embed_api_base: str,
        embed_api_key: str,
        embed_model: str,
        embed_dimensions: int,
        pool: Any | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> RagAgentPgRetriever:
        owns_pool = pool is None
        owns_client = client is None
        created_pool = pool
        created_client = client
        retriever: RagAgentPgRetriever | None = None
        try:
            if created_pool is None:
                import asyncpg

                created_pool = await asyncpg.create_pool(dsn=dsn)
            if created_client is None:
                created_client = httpx.AsyncClient()
            retriever = cls(
                dsn=dsn,
                demo_tenant=demo_tenant,
                embed_api_base=embed_api_base,
                embed_api_key=embed_api_key,
                embed_model=embed_model,
                embed_dimensions=embed_dimensions,
                pool=created_pool,
                client=created_client,
                owns_pool=owns_pool,
                owns_client=owns_client,
            )
            await retriever._probe_dependencies()
            return retriever
        except Exception as exc:  # noqa: BLE001 - sanitize dependency failures
            if retriever is not None:
                await retriever.close()
            else:
                if owns_client and created_client is not None:
                    await cls._safe_close(created_client, "aclose", "client")
                if owns_pool and created_pool is not None:
                    await cls._safe_close(created_pool, "close", "pool")
            _raise_unavailable("startup", exc)

    async def similarity_search(
        self,
        query: str,
        *,
        tenant_id: str,
        k: int = 5,
    ) -> list[KnowledgeHit]:
        if tenant_id != self._demo_tenant:
            return []

        try:
            embedding = await self._embed(query)
        except Exception as exc:  # noqa: BLE001 - sanitize embedding failures
            _raise_unavailable("embedding", exc)

        vector_literal = "[" + ",".join(str(value) for value in embedding) + "]"
        try:
            async with (
                self._pool.acquire() as connection,
                connection.transaction(readonly=True),
            ):
                rows = await connection.fetch(
                    _SIMILARITY_SEARCH_SQL,
                    vector_literal,
                    int(k),
                )
            return [self._map_hit(row) for row in rows]
        except Exception as exc:  # noqa: BLE001 - sanitize database failures
            _raise_unavailable("query", exc)

    async def health_check(self) -> dict[str, Any]:
        try:
            await self._probe_dependencies()
        except Exception as exc:  # noqa: BLE001 - sanitize dependency failures
            _raise_unavailable("health", exc)
        return {"status": "ok", "backend": _BACKEND}

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            await self._safe_close(self._client, "aclose", "client")
            self._owns_client = False
        if self._owns_pool:
            await self._safe_close(self._pool, "close", "pool")
            self._owns_pool = False

    @staticmethod
    async def _safe_close(resource: Any, method_name: str, kind: str) -> None:
        try:
            await getattr(resource, method_name)()
        except Exception as exc:  # noqa: BLE001 - cleanup is best effort
            logger.warning(
                "RAG-Agent resource close failed kind=%s error_type=%s",
                kind,
                type(exc).__name__,
            )

    async def _probe_dependencies(self) -> None:
        if self._embed_model != _EXPECTED_MODEL:
            raise _CapabilityFailure(
                "configured embedding model must be BAAI/bge-m3"
            )
        if self._embed_dimensions != _EXPECTED_DIMENSIONS:
            raise _CapabilityFailure(
                "configured embedding dimension must be 512"
            )
        async with (
            self._pool.acquire() as connection,
            connection.transaction(readonly=True),
        ):
            extversion = await connection.fetchval(_EXTENSION_PROBE_SQL)
            if not extversion:
                raise _CapabilityFailure("vector extension is absent")

            tables = await connection.fetchrow(_TABLES_PROBE_SQL)
            if tables is None or any(tables[index] is None for index in range(3)):
                raise _CapabilityFailure(
                    "required RAG-Agent knowledge table is absent"
                )

            embedding_type = await connection.fetchval(
                _EMBEDDING_TYPE_PROBE_SQL
            )
            if embedding_type != "vector(512)":
                raise _CapabilityFailure(
                    "kb_chunk.embedding must be vector(512)"
                )
        await self._embed("AgentBridge startup probe")

    async def _embed(self, query: str) -> list[float]:
        headers = (
            {"Authorization": f"Bearer {self._embed_api_key}"}
            if self._embed_api_key
            else {}
        )
        response = await self._client.post(
            f"{self._embed_api_base}/embeddings",
            json={"model": self._embed_model, "input": [query]},
            headers=headers,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise _CapabilityFailure("embedding response must be an object")
        data = body.get("data")
        if not isinstance(data, list) or len(data) != 1:
            raise _CapabilityFailure(
                "embedding response must contain exactly one data item"
            )
        item = data[0]
        if not isinstance(item, dict):
            raise _CapabilityFailure("embedding data item must be an object")
        embedding = item.get("embedding")
        if not isinstance(embedding, list):
            raise _CapabilityFailure("embedding must be a list")
        if len(embedding) != _EXPECTED_DIMENSIONS:
            raise _CapabilityFailure("embedding dimension must be 512")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in embedding
        ):
            raise _CapabilityFailure("embedding values must be finite numbers")
        return [float(value) for value in embedding]

    def _map_hit(self, row: Any) -> KnowledgeHit:
        score = float(row["score"])
        if not math.isfinite(score):
            raise _CapabilityFailure("knowledge score must be finite")
        return {
            "chunk_id": str(row["chunk_id"]),
            "doc_id": str(row["doc_id"]),
            "text": str(row["text"]),
            "tenant_id": self._demo_tenant,
            "score": min(1.0, max(0.0, score)),
            "metadata": {
                "title": row["title"],
                "section_id": row["section_id"],
                "heading": row["heading"],
                "source_backend": _BACKEND,
            },
        }
