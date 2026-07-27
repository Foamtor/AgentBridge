"""External RAG retriever tests."""

from __future__ import annotations

import httpx
import pytest

from adapters.external_rag_retriever import ExternalRagRetriever, map_external_hits


def test_map_external_hits_drops_wrong_tenant() -> None:
    hits = map_external_hits(
        [
            {
                "chunk_id": "c1",
                "doc_id": "d1",
                "text": "allowed",
                "tenant_id": "acme",
                "score": 0.9,
            },
            {
                "chunk_id": "c2",
                "doc_id": "d2",
                "text": "blocked",
                "tenant_id": "other",
            },
        ],
        tenant_id="acme",
    )
    assert len(hits) == 1
    assert hits[0]["chunk_id"] == "c1"
    assert hits[0]["tenant_id"] == "acme"


def test_map_external_hits_aliases_id_and_content() -> None:
    hits = map_external_hits(
        [{"id": "c9", "content": "hello external", "tenant_id": "acme"}],
        tenant_id="acme",
    )
    assert len(hits) == 1
    assert hits[0]["chunk_id"] == "c9"
    assert hits[0]["text"] == "hello external"


@pytest.mark.asyncio
async def test_external_retriever_calls_protocol_endpoint() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        import json

        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "chunk_id": "c1",
                        "doc_id": "d1",
                        "text": "refund policy",
                        "tenant_id": "acme",
                        "score": 0.8,
                    }
                ],
                "retrieval_mode": "hybrid",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock") as client:
        retriever = ExternalRagRetriever(
            base_url="http://mock",
            api_key="secret",
            client=client,
        )
        hits = await retriever.similarity_search("refund", tenant_id="acme", k=3)

    assert seen["path"] == "/v1/retrieve"
    assert seen["body"]["tenant_id"] == "acme"
    assert seen["body"]["top_k"] == 3
    assert len(hits) == 1
    assert hits[0]["chunk_id"] == "c1"


@pytest.mark.asyncio
async def test_external_retriever_empty_hits_on_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(504, json={"error": "timeout"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock") as client:
        retriever = ExternalRagRetriever(
            base_url="http://mock",
            failure_policy="empty_hits",
            client=client,
        )
        hits = await retriever.similarity_search("x", tenant_id="acme")
    assert hits == []


@pytest.mark.asyncio
async def test_external_health_check() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/health":
            return httpx.Response(200, json={"status": "ok", "detail": "ready"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock") as client:
        retriever = ExternalRagRetriever(base_url="http://mock", client=client)
        health = await retriever.health_check()
    assert health["status"] == "ok"
