"""Knowledge status provider unit tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from adapters.knowledge_status import KnowledgeStatusProvider
from agentbridge_core.errors import KnowledgeBackendUnavailable


@pytest.mark.asyncio
async def test_fake_backend_status_skips_embedding() -> None:
    settings = SimpleNamespace(
        knowledge_backend="fake",
        embed_model="text-embedding-3-small",
    )
    provider = KnowledgeStatusProvider(settings, retriever=object())
    body = await provider.get_status(tenant_id="acme")
    assert body["backend"] == "fake"
    assert body["tenant_id"] == "acme"
    assert body["scope"] == "tenant"
    assert body["healthy"] is True
    assert body["tenant_id"] == "acme"
    assert body["embedding"]["status"] == "skipped"
    assert body["ingest_jobs"] == []


@pytest.mark.asyncio
async def test_langchain_pg_probe_ok() -> None:
    settings = SimpleNamespace(
        knowledge_backend="langchain_pg",
        embed_model="text-embedding-3-small",
    )
    embeddings = SimpleNamespace(aembed_query=AsyncMock(return_value=[0.1]))
    retriever = SimpleNamespace(_embeddings=embeddings)
    provider = KnowledgeStatusProvider(settings, retriever)
    body = await provider.get_status(tenant_id="acme")
    assert body["healthy"] is True
    assert body["embedding"]["status"] == "ok"
    embeddings.aembed_query.assert_awaited_once_with("health")


@pytest.mark.asyncio
async def test_langchain_pg_probe_failure_degrades() -> None:
    settings = SimpleNamespace(
        knowledge_backend="langchain_pg",
        embed_model="text-embedding-3-small",
    )
    embeddings = SimpleNamespace(aembed_query=AsyncMock(side_effect=RuntimeError("tei down")))
    retriever = SimpleNamespace(_embeddings=embeddings)
    provider = KnowledgeStatusProvider(settings, retriever)
    body = await provider.get_status(tenant_id="acme")
    assert body["healthy"] is False
    assert body["embedding"]["status"] == "degraded"


@pytest.mark.asyncio
async def test_rag_agent_pg_status_delegates_to_retriever_health() -> None:
    expected_health = {
        "status": "fail",
        "message": "read-only dependency unavailable",
    }

    class HealthRetriever:
        def __init__(self) -> None:
            self.calls = 0

        async def health_check(self) -> dict[str, str]:
            self.calls += 1
            return expected_health

    settings = SimpleNamespace(
        knowledge_backend="rag_agent_pg",
        rag_agent_embed_model="BAAI/bge-m3",
    )
    retriever = HealthRetriever()
    provider = KnowledgeStatusProvider(settings, retriever)

    body = await provider.get_status(tenant_id="rag-agent-demo")

    assert retriever.calls == 1
    assert body["backend"] == "rag_agent_pg"
    assert body["healthy"] is False
    assert body["health"] == expected_health
    assert body["embedding"]["model"] == "BAAI/bge-m3"


@pytest.mark.asyncio
async def test_rag_agent_pg_status_sanitizes_health_check_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "postgresql://admin:dsn-secret@db/rag credential-secret"

    class ThrowingRetriever:
        async def health_check(self) -> dict[str, str]:
            raise KnowledgeBackendUnavailable(secret)

    settings = SimpleNamespace(
        knowledge_backend="rag_agent_pg",
        rag_agent_embed_model="BAAI/bge-m3",
    )
    provider = KnowledgeStatusProvider(settings, ThrowingRetriever())

    body = await provider.get_status(tenant_id="rag-agent-demo")

    assert body["healthy"] is False
    assert body["health"] == {
        "status": "fail",
        "message": "knowledge backend unavailable",
    }
    assert secret not in str(body)
    assert secret not in caplog.text
