"""External RAG HTTP retriever (KNOWLEDGE_BACKEND=external)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from agentbridge_core.protocol.knowledge import (
    KnowledgeHit,
    doc_to_knowledge_hit,
    require_tenant_id,
)

logger = logging.getLogger(__name__)


def map_external_hits(
    hits: list[dict[str, Any]], *, tenant_id: str
) -> list[KnowledgeHit]:
    """Map downstream hits to KnowledgeHit; drop tenant mismatches."""
    tid = require_tenant_id(tenant_id)
    out: list[KnowledgeHit] = []
    for raw in hits:
        if not isinstance(raw, dict):
            continue
        hit_tenant = raw.get("tenant_id")
        if hit_tenant is not None and str(hit_tenant).strip() and str(hit_tenant).strip() != tid:
            logger.warning(
                "dropping external hit with tenant_id=%r (expected %r)",
                hit_tenant,
                tid,
            )
            continue
        chunk_id = raw.get("chunk_id") or raw.get("id")
        if not chunk_id:
            logger.warning("dropping external hit without chunk_id/id")
            continue
        text = raw.get("text") or raw.get("content")
        if text is None or str(text) == "":
            logger.warning("dropping external hit %s without text", chunk_id)
            continue
        mapped: dict[str, Any] = {
            "chunk_id": str(chunk_id),
            "doc_id": str(raw.get("doc_id") or chunk_id),
            "text": str(text),
            "tenant_id": tid,
            "metadata": dict(raw.get("metadata") or {}),
        }
        score = raw.get("score")
        try:
            hit = doc_to_knowledge_hit(
                mapped,
                tenant_id=tid,
                score=float(score) if score is not None else None,
            )
        except (ValueError, TypeError):
            logger.warning("dropping invalid external hit %s", chunk_id, exc_info=True)
            continue
        if raw.get("section_anchor") is not None:
            hit["section_anchor"] = raw.get("section_anchor")
        if raw.get("jump_url") is not None:
            hit["jump_url"] = raw.get("jump_url")
        out.append(hit)
    return out


class ExternalRagRetriever:
    """POST {base}/v1/retrieve adapter per external-rag-protocol."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        timeout_seconds: float = 5.0,
        failure_policy: str = "empty_hits",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._failure_policy = (failure_policy or "empty_hits").strip().lower()
        self._client = client
        self._owned_client: httpx.AsyncClient | None = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        if self._owned_client is None:
            self._owned_client = httpx.AsyncClient(timeout=self._timeout)
        return self._owned_client

    async def close(self) -> None:
        if self._owned_client is not None:
            await self._owned_client.aclose()
            self._owned_client = None

    async def health_check(self) -> dict[str, Any]:
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self._base_url}/v1/health",
                headers=self._headers(),
            )
            resp.raise_for_status()
            body = resp.json()
            if not isinstance(body, dict):
                return {"status": "degraded", "message": "invalid health payload"}
            status = str(body.get("status") or "ok")
            return {"status": status, "detail": body.get("detail")}
        except Exception as exc:  # noqa: BLE001
            logger.warning("external RAG health check failed", exc_info=True)
            return {"status": "fail", "message": str(exc)}

    async def similarity_search(
        self,
        query: str,
        *,
        tenant_id: str,
        k: int = 5,
    ) -> list[KnowledgeHit]:
        tid = require_tenant_id(tenant_id)
        client = await self._get_client()
        payload = {
            "query": query,
            "tenant_id": tid,
            "top_k": k,
            "options": {},
        }
        try:
            resp = await client.post(
                f"{self._base_url}/v1/retrieve",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:
            if self._failure_policy == "fail_run":
                raise
            logger.warning(
                "external RAG retrieve failed; returning empty hits",
                exc_info=True,
            )
            return []
        if not isinstance(body, dict):
            return []
        raw_hits = body.get("hits")
        if not isinstance(raw_hits, list):
            return []
        return map_external_hits(raw_hits, tenant_id=tid)

    async def ingest(
        self,
        docs: list[dict[str, Any]],
        *,
        tenant_id: str,
    ) -> int:
        raise NotImplementedError("external backend ingest is not supported")
