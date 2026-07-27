"""Knowledge status provider unit tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from adapters.knowledge_status import KnowledgeStatusProvider


@pytest.mark.asyncio
async def test_fake_backend_status_skips_embedding() -> None:
    settings = SimpleNamespace(
        knowledge_backend="fake",
        embed_model="text-embedding-3-small",
    )
    provider = KnowledgeStatusProvider(settings, retriever=object())
    body = await provider.get_status(tenant_id="acme")
    assert body["backend"] == "fake"
    assert body["healthy"] is True
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
