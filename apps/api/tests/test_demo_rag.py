"""demo_rag stream emits x.bridge.citation."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from adapters.external_rag_retriever import ExternalRagRetriever
from agent_base_core.adapters.fake_retriever import FakeRetriever
from fastapi.testclient import TestClient
from domains.demo_rag.graph import _cite


def _parse_sse(body: str) -> list[dict]:
    events: list[dict] = []
    for block in body.split("\n\n"):
        line = block.strip()
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[len("data: ") :]))
    return events


@pytest.mark.asyncio
async def test_demo_rag_emits_citation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "0")
    import os

    os.environ["AGENT_BASE_FAKE_RUNTIME"] = "0"
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    fake = FakeRetriever()
    await fake.ingest(
        [{"chunk_id": "d1", "doc_id": "doc-1", "text": "refund policy 30 days"}],
        tenant_id="dev",
    )
    with TestClient(app) as c:
        c.app.state.retriever = fake
        r = c.post(
            "/chat/stream",
            json={
                "query": "refund policy",
                "thread_id": "t-rag-1",
                "route": "demo_rag",
            },
        )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]
    assert "x.bridge.citation" in types
    cite = next(e for e in events if e["type"] == "x.bridge.citation")
    assert cite["data"]["route"] == "demo_rag"
    c0 = cite["data"]["citations"][0]
    assert c0["chunk_id"] == "d1"
    assert c0["doc_id"] == "doc-1"
    assert "refund" in c0["text"]
    assert c0["tenant_id"] == "dev"


@pytest.mark.asyncio
async def test_demo_rag_external_emits_citation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "0")
    monkeypatch.setenv("KNOWLEDGE_BACKEND", "external")
    monkeypatch.setenv("KB_EXTERNAL_BASE_URL", "http://mock-rag")
    import os

    os.environ["AGENT_BASE_FAKE_RUNTIME"] = "0"
    os.environ["KNOWLEDGE_BACKEND"] = "external"
    os.environ["KB_EXTERNAL_BASE_URL"] = "http://mock-rag"
    from testing.app_factory import create_test_app as create_app

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/retrieve":
            return httpx.Response(
                200,
                json={
                    "hits": [
                        {
                            "chunk_id": "ext-1",
                            "doc_id": "doc-ext",
                            "text": "external refund policy",
                            "tenant_id": "dev",
                            "score": 0.88,
                        }
                    ]
                },
            )
        if request.url.path == "/v1/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://mock-rag",
    ) as client:
        app = create_app()
        with TestClient(app) as c:
            c.app.state.retriever = ExternalRagRetriever(
                base_url="http://mock-rag",
                client=client,
            )
            r = c.post(
                "/chat/stream",
                json={
                    "query": "refund policy",
                    "thread_id": "t-rag-ext-1",
                    "route": "demo_rag",
                },
            )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    cite = next(e for e in events if e["type"] == "x.bridge.citation")
    c0 = cite["data"]["citations"][0]
    assert c0["chunk_id"] == "ext-1"
    assert c0["doc_id"] == "doc-ext"
    assert c0["tenant_id"] == "dev"


def test_cite_skips_invalid_citation_items() -> None:
    state = {
        "messages": [
            SimpleNamespace(
                name="search_knowledge",
                content=[
                    {
                        "chunk_id": "ok-1",
                        "doc_id": "doc-ok",
                        "text": "valid hit",
                        "tenant_id": "dev",
                    },
                    {
                        "chunk_id": "",
                        "doc_id": "doc-bad",
                        "text": "invalid hit",
                        "tenant_id": "dev",
                    },
                ],
            )
        ]
    }
    payload = _cite(state)
    citations = payload["outbound_extensions"][0]["data"]["citations"]
    assert len(citations) == 1
    assert citations[0]["chunk_id"] == "ok-1"
