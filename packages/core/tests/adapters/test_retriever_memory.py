"""Retriever + MemoryStore timeout tests."""

from __future__ import annotations

import asyncio

import pytest
from agent_base_core.adapters.fake_retriever import FakeRetriever
from agent_base_core.adapters.timeout_memory_store import TimeoutMemoryStore
from agent_base_core.protocol.context import RunContext


@pytest.mark.asyncio
async def test_retriever_tenant_isolation() -> None:
    r = FakeRetriever()
    await r.ingest(
        [{"id": "1", "text": "alpha refund", "tenant_id": "acme"}],
        tenant_id="acme",
    )
    hits = await r.similarity_search("refund", tenant_id="acme")
    assert hits
    assert await r.similarity_search("refund", tenant_id="other") == []


@pytest.mark.asyncio
async def test_memory_recall_timeout_returns_empty() -> None:
    async def slow(query: str, ctx: RunContext):
        await asyncio.sleep(1.0)
        return [{"text": query}]

    store = TimeoutMemoryStore(slow)
    out = await store.recall("x", ctx=RunContext(), timeout=0.05)
    assert out == []
