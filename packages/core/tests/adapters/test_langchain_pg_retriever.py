"""LangchainPgRetriever unit tests with injected fake store."""

from __future__ import annotations

import logging

import pytest
from agentbridge_core.adapters.langchain_pg_retriever import (
    LangchainPgRetriever,
    _sqlalchemy_dsn,
)
from langchain_core.documents import Document


def test_sqlalchemy_dsn_uses_installed_asyncpg_dialect() -> None:
    assert _sqlalchemy_dsn("postgresql://user:pass@db/knowledge") == (
        "postgresql+asyncpg://user:pass@db/knowledge"
    )
    assert _sqlalchemy_dsn("postgresql+asyncpg://user:pass@db/knowledge") == (
        "postgresql+asyncpg://user:pass@db/knowledge"
    )


class _FakeStore:
    def __init__(self) -> None:
        self.docs: list[Document] = []

    async def aadd_documents(self, documents: list[Document], **kwargs):
        self.docs.extend(documents)
        return [d.metadata.get("chunk_id") for d in documents]

    async def asimilarity_search_with_score(self, query: str, k: int = 5, filter=None):
        tid = (filter or {}).get("tenant_id")
        out = []
        for d in self.docs:
            if tid is not None and d.metadata.get("tenant_id") != tid:
                continue
            if query.lower() in (d.page_content or "").lower():
                out.append((d, 0.42))
        return out[:k]


class _BoomStore(_FakeStore):
    async def asimilarity_search_with_score(self, query: str, k: int = 5, filter=None):
        raise RuntimeError("tei down")


@pytest.mark.asyncio
async def test_langchain_pg_tenant_isolation() -> None:
    store = _FakeStore()
    r = LangchainPgRetriever(store=store, embeddings=None)
    await r.ingest(
        [{"chunk_id": "c1", "doc_id": "d1", "text": "refund policy"}],
        tenant_id="acme",
    )
    await r.ingest(
        [{"chunk_id": "c2", "doc_id": "d2", "text": "refund policy"}],
        tenant_id="other",
    )
    hits = await r.similarity_search("refund", tenant_id="acme", k=5)
    assert len(hits) == 1
    assert hits[0]["chunk_id"] == "c1"
    assert hits[0]["tenant_id"] == "acme"
    assert len(await r.similarity_search("refund", tenant_id="other")) == 1
    assert len(await r.similarity_search("refund", tenant_id="ghost")) == 0


@pytest.mark.asyncio
async def test_langchain_pg_search_degrades_to_empty(caplog) -> None:
    r = LangchainPgRetriever(store=_BoomStore(), embeddings=None)
    with caplog.at_level(logging.WARNING):
        hits = await r.similarity_search("refund", tenant_id="acme")
    assert hits == []


@pytest.mark.asyncio
async def test_langchain_pg_rejects_blank_tenant() -> None:
    r = LangchainPgRetriever(store=_FakeStore(), embeddings=None)
    with pytest.raises(ValueError, match="tenant_id"):
        await r.similarity_search("x", tenant_id="")
