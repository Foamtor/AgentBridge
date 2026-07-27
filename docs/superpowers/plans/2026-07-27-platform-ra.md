# Platform R-A (langchain_pg) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship R-A: unified `KnowledgeHit`, Fake + `langchain_pg` retrievers, TEI embeddings, tenant isolation, and `demo_rag` citations — without HTTP `/ingest`.

**Architecture:** Extend the existing `Retriever` Port in `packages/core`. Add `KnowledgeHit` + normalize helpers. Keep `FakeRetriever` for CI. Add `LangchainPgRetriever` (lazy-import `langchain_postgres` / OpenAI-compatible embeddings) assembled only in `apps/api/lifespan.py` when `KNOWLEDGE_BACKEND=langchain_pg`. Single PG collection/table with dedicated `tenant_id` column for filters. Domains only call Port methods.

**Tech Stack:** Python 3.12, TypedDict, FastAPI lifespan, `langchain-postgres` + `langchain-openai` (OpenAI-compatible → local TEI), PostgreSQL 16 + pgvector (`compose --profile rag`), pytest, import-linter.

**Design spec:** [../specs/2026-07-27-platform-ra-design.md](../specs/2026-07-27-platform-ra-design.md)  
**Parent map:** [./2026-07-27-plan6-rag-production.md](./2026-07-27-plan6-rag-production.md) (R-A / T1–T8)

## Global Constraints

- `application` must not import `adapters`
- Domains must not import `langchain_postgres`, `langchain_openai`, or other engine SDKs
- Adapters constructed only in `apps/api/lifespan.py`
- Port method names: `similarity_search`, `ingest` (no parallel `search` truth)
- Empty / blank `tenant_id` → raise `ValueError` (never default to `"default"`)
- Cross-tenant search → empty list (no leak)
- Runtime TEI/PG failure on search → empty list + log (do not 500 the chat)
- Missing `rag` extra / embed config when `KNOWLEDGE_BACKEND=langchain_pg` → **startup failure**
- R-A: vector similarity only (no hybrid); no HTTP `/ingest`; no `KnowledgeIngest` Port
- Optional extra name pinned: **`rag`**
- `k` default **5**; `demo_rag` may pass `k=3`
- Citation envelope: `data.route` + `data.citations[]` as `KnowledgeHit` fields
- Default CI must stay green without pgvector/TEI

## File map

| File | Responsibility |
|------|----------------|
| `packages/core/src/agent_base_core/protocol/knowledge.py` | `KnowledgeHit` TypedDict + `require_tenant_id` + `normalize_ingest_doc` + `doc_to_knowledge_hit` |
| `packages/core/src/agent_base_core/ports/retriever.py` | Port signatures → `list[KnowledgeHit]`, `k: int = 5` |
| `packages/core/src/agent_base_core/adapters/fake_retriever.py` | In-memory backend aligned to KnowledgeHit |
| `packages/core/src/agent_base_core/adapters/langchain_pg_retriever.py` | PG+TEI backend (lazy imports) |
| `packages/core/pyproject.toml` | optional-deps `rag` |
| `apps/api/pyproject.toml` | re-export/extra `rag` depending on core |
| `apps/api/config/settings.py` | `knowledge_backend`, `kb_dsn`, `embed_*` |
| `apps/api/lifespan.py` | `_build_retriever` + teardown |
| `apps/api/domains/demo_rag/graph.py` | citation fields |
| `apps/api/migrations/003_knowledge_pgvector.sql` | schema/table for filterable `tenant_id` |
| `scripts/ingest_demo_rag.py` | seed helper using KnowledgeHit fields |
| `scripts/import_scan_domains_rag.py` | forbid engine imports under `apps/api/domains` |
| `.importlinter` | register new adapter module in independence contract if required |
| `.env.example`, `docs/knowledge-base.md`, `docs/deploy.md` | R-A ops notes |
| tests under `packages/core/tests/...`, `apps/api/tests/...` | Fake + mocked langchain_pg + demo_rag |

---

### Task 1: KnowledgeHit + normalize helpers + Port

**Files:**
- Create: `packages/core/src/agent_base_core/protocol/knowledge.py`
- Modify: `packages/core/src/agent_base_core/ports/retriever.py`
- Create: `packages/core/tests/protocol/test_knowledge.py`

**Interfaces:**
- Consumes: none
- Produces:
  - `KnowledgeHit` TypedDict
  - `require_tenant_id(tenant_id: str) -> str`
  - `normalize_ingest_doc(doc: dict, *, tenant_id: str) -> dict`
  - `doc_to_knowledge_hit(doc: dict, *, tenant_id: str, score: float | None = None) -> KnowledgeHit`
  - `Retriever.similarity_search(..., k: int = 5) -> list[KnowledgeHit]`
  - `Retriever.ingest(docs, *, tenant_id: str) -> int`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/protocol/test_knowledge.py
import pytest
from agent_base_core.protocol.knowledge import (
    require_tenant_id,
    normalize_ingest_doc,
    doc_to_knowledge_hit,
)


def test_require_tenant_id_rejects_blank() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        require_tenant_id("")
    with pytest.raises(ValueError, match="tenant_id"):
        require_tenant_id("   ")


def test_normalize_maps_id_and_fills_doc_id() -> None:
    out = normalize_ingest_doc(
        {"id": "c1", "text": "hello"},
        tenant_id="acme",
    )
    assert out["chunk_id"] == "c1"
    assert out["doc_id"] == "c1"
    assert out["text"] == "hello"
    assert out["tenant_id"] == "acme"


def test_normalize_rejects_conflicting_tenant() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        normalize_ingest_doc(
            {"chunk_id": "c1", "text": "x", "tenant_id": "other"},
            tenant_id="acme",
        )


def test_doc_to_knowledge_hit_required_fields() -> None:
    hit = doc_to_knowledge_hit(
        {"chunk_id": "c1", "doc_id": "d1", "text": "t", "tenant_id": "acme"},
        tenant_id="acme",
        score=0.9,
    )
    assert hit["chunk_id"] == "c1"
    assert hit["doc_id"] == "d1"
    assert hit["text"] == "t"
    assert hit["tenant_id"] == "acme"
    assert hit["score"] == 0.9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest packages/core/tests/protocol/test_knowledge.py -v`  
Expected: FAIL (module not found)

- [ ] **Step 3: Write minimal implementation**

```python
# packages/core/src/agent_base_core/protocol/knowledge.py
"""Unified knowledge hit contract (R-A)."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class KnowledgeHit(TypedDict):
    chunk_id: str
    doc_id: str
    text: str
    tenant_id: str
    score: NotRequired[float | None]
    metadata: NotRequired[dict[str, Any]]
    section_anchor: NotRequired[str | None]
    jump_url: NotRequired[str | None]


def require_tenant_id(tenant_id: str) -> str:
    if tenant_id is None or not str(tenant_id).strip():
        raise ValueError("tenant_id is required and must be non-blank")
    return str(tenant_id).strip()


def normalize_ingest_doc(doc: dict[str, Any], *, tenant_id: str) -> dict[str, Any]:
    tid = require_tenant_id(tenant_id)
    text = doc.get("text")
    if text is None or str(text) == "":
        raise ValueError("ingest doc requires non-empty text")
    chunk_id = doc.get("chunk_id") or doc.get("id")
    if not chunk_id:
        raise ValueError("ingest doc requires chunk_id or id")
    chunk_id = str(chunk_id)
    doc_id = str(doc.get("doc_id") or chunk_id)
    existing = doc.get("tenant_id")
    if existing is not None and str(existing).strip() and str(existing).strip() != tid:
        raise ValueError(
            f"doc tenant_id {existing!r} conflicts with parameter tenant_id {tid!r}"
        )
    meta = dict(doc.get("metadata") or {})
    # Preserve extra keys (except reserved) into metadata
    reserved = {
        "id",
        "chunk_id",
        "doc_id",
        "text",
        "tenant_id",
        "metadata",
        "score",
        "section_anchor",
        "jump_url",
    }
    for k, v in doc.items():
        if k not in reserved:
            meta.setdefault(k, v)
    out: dict[str, Any] = {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "text": str(text),
        "tenant_id": tid,
        "metadata": meta,
    }
    if "section_anchor" in doc:
        out["section_anchor"] = doc.get("section_anchor")
    if "jump_url" in doc:
        out["jump_url"] = doc.get("jump_url")
    return out


def doc_to_knowledge_hit(
    doc: dict[str, Any],
    *,
    tenant_id: str,
    score: float | None = None,
) -> KnowledgeHit:
    tid = require_tenant_id(tenant_id)
    normalized = normalize_ingest_doc(doc, tenant_id=tid) if "text" in doc else doc
    hit_tenant = require_tenant_id(str(normalized.get("tenant_id") or tid))
    if hit_tenant != tid:
        raise ValueError("hit tenant_id does not match request tenant_id")
    hit: KnowledgeHit = {
        "chunk_id": str(normalized["chunk_id"]),
        "doc_id": str(normalized.get("doc_id") or normalized["chunk_id"]),
        "text": str(normalized["text"]),
        "tenant_id": hit_tenant,
    }
    if score is not None:
        hit["score"] = score
    elif "score" in normalized:
        hit["score"] = normalized.get("score")
    meta = normalized.get("metadata")
    if isinstance(meta, dict) and meta:
        hit["metadata"] = dict(meta)
    if normalized.get("section_anchor") is not None:
        hit["section_anchor"] = normalized.get("section_anchor")
    if normalized.get("jump_url") is not None:
        hit["jump_url"] = normalized.get("jump_url")
    return hit
```

```python
# packages/core/src/agent_base_core/ports/retriever.py
"""Retriever protocol — tenant-scoped similarity search."""

from __future__ import annotations

from typing import Any, Protocol

from agent_base_core.protocol.knowledge import KnowledgeHit


class Retriever(Protocol):
    async def similarity_search(
        self,
        query: str,
        *,
        tenant_id: str,
        k: int = 5,
    ) -> list[KnowledgeHit]: ...

    async def ingest(
        self,
        docs: list[dict[str, Any]],
        *,
        tenant_id: str,
    ) -> int: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest packages/core/tests/protocol/test_knowledge.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/agent_base_core/protocol/knowledge.py packages/core/src/agent_base_core/ports/retriever.py packages/core/tests/protocol/test_knowledge.py
git commit -m "feat(core): add KnowledgeHit contract and Retriever Port defaults"
```

---

### Task 2: Align FakeRetriever + tenant tests

**Files:**
- Modify: `packages/core/src/agent_base_core/adapters/fake_retriever.py`
- Modify: `packages/core/tests/adapters/test_retriever_memory.py`

**Interfaces:**
- Consumes: `require_tenant_id`, `normalize_ingest_doc`, `doc_to_knowledge_hit`
- Produces: `FakeRetriever` returning `list[KnowledgeHit]`; rejects blank tenant; maps old `id`

- [ ] **Step 1: Write the failing tests (extend existing file)**

Replace/extend `packages/core/tests/adapters/test_retriever_memory.py` retriever tests:

```python
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
    assert hits[0]["chunk_id"] == "1"
    assert hits[0]["doc_id"] == "1"
    assert hits[0]["tenant_id"] == "acme"
    assert "text" in hits[0]
    assert await r.similarity_search("refund", tenant_id="other") == []


@pytest.mark.asyncio
async def test_retriever_rejects_blank_tenant() -> None:
    r = FakeRetriever()
    with pytest.raises(ValueError, match="tenant_id"):
        await r.similarity_search("x", tenant_id="")
    with pytest.raises(ValueError, match="tenant_id"):
        await r.ingest([{"id": "1", "text": "t"}], tenant_id="  ")


@pytest.mark.asyncio
async def test_retriever_rejects_conflicting_doc_tenant() -> None:
    r = FakeRetriever()
    with pytest.raises(ValueError, match="tenant_id"):
        await r.ingest(
            [{"chunk_id": "1", "text": "t", "tenant_id": "other"}],
            tenant_id="acme",
        )


@pytest.mark.asyncio
async def test_memory_recall_timeout_returns_empty() -> None:
    async def slow(query: str, ctx: RunContext):
        await asyncio.sleep(1.0)
        return [{"text": query}]

    store = TimeoutMemoryStore(slow)
    out = await store.recall("x", ctx=RunContext(), timeout=0.05)
    assert out == []
```

- [ ] **Step 2: Run tests to verify new assertions fail or old shape breaks**

Run: `python -m pytest packages/core/tests/adapters/test_retriever_memory.py -v`  
Expected: FAIL on KnowledgeHit fields and/or blank tenant (until Fake updated)

- [ ] **Step 3: Implement FakeRetriever**

```python
# packages/core/src/agent_base_core/adapters/fake_retriever.py
"""In-memory Retriever with tenant namespaces (no pgvector required)."""

from __future__ import annotations

from typing import Any

from agent_base_core.protocol.knowledge import (
    KnowledgeHit,
    doc_to_knowledge_hit,
    normalize_ingest_doc,
    require_tenant_id,
)


class FakeRetriever:
    def __init__(self) -> None:
        self._docs: dict[str, list[dict[str, Any]]] = {}

    async def ingest(
        self, docs: list[dict[str, Any]], *, tenant_id: str
    ) -> int:
        tid = require_tenant_id(tenant_id)
        # Fail entire batch on any bad doc (spec: whole ingest fails)
        normalized = [normalize_ingest_doc(d, tenant_id=tid) for d in docs]
        bucket = self._docs.setdefault(tid, [])
        for d in normalized:
            bucket.append(d)
        return len(normalized)

    async def similarity_search(
        self, query: str, *, tenant_id: str, k: int = 5
    ) -> list[KnowledgeHit]:
        tid = require_tenant_id(tenant_id)
        q = query.lower()
        scored: list[tuple[int, dict[str, Any]]] = []
        for doc in self._docs.get(tid, []):
            text = str(doc.get("text") or "")
            score = sum(1 for w in q.split() if w and w in text.lower())
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[KnowledgeHit] = []
        for score, doc in scored[:k]:
            hit = doc_to_knowledge_hit(doc, tenant_id=tid, score=float(score))
            if hit["tenant_id"] != tid:
                continue
            out.append(hit)
        return out
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest packages/core/tests/adapters/test_retriever_memory.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/agent_base_core/adapters/fake_retriever.py packages/core/tests/adapters/test_retriever_memory.py
git commit -m "feat(core): align FakeRetriever with KnowledgeHit and tenant rules"
```

---

### Task 3: Add `rag` optional extra

**Files:**
- Modify: `packages/core/pyproject.toml`
- Modify: `apps/api/pyproject.toml`

**Interfaces:**
- Consumes: none
- Produces: installable extra named exactly `rag`

- [ ] **Step 1: Add extras (no separate failing test — verify via pip show / import attempt)**

In `packages/core/pyproject.toml` under `[project.optional-dependencies]`, add:

```toml
rag = [
  "langchain-postgres>=0.0.14",
  "langchain-openai>=0.2",
  "asyncpg>=0.29,<1",
]
```

In `apps/api/pyproject.toml` under `[project.optional-dependencies]`, add:

```toml
rag = [
  "agent-base-core[rag]",
]
```

(Keep existing `dev`, `datasource`, `redis` extras.)

- [ ] **Step 2: Verify default install still imports Fake without rag**

Run:

```bash
python -c "from agent_base_core.adapters.fake_retriever import FakeRetriever; print('ok')"
```

Expected: prints `ok` without requiring langchain-postgres.

- [ ] **Step 3: Commit**

```bash
git add packages/core/pyproject.toml apps/api/pyproject.toml
git commit -m "build: add rag optional extra for langchain_pg"
```

---

### Task 4: LangchainPgRetriever (unit-tested with injected fake store)

**Files:**
- Create: `packages/core/src/agent_base_core/adapters/langchain_pg_retriever.py`
- Create: `packages/core/tests/adapters/test_langchain_pg_retriever.py`
- Modify: `.importlinter` (add module to independence list **or** leave out of independence set if new leaf — prefer add to modules list as independent leaf)

**Interfaces:**
- Consumes: knowledge helpers; optional injected `store` for tests
- Produces:
  - `LangchainPgRetriever(store=..., embeddings=...)` for tests
  - `LangchainPgRetriever.create(dsn=..., embed_api_base=..., embed_model=..., embed_dimensions=..., embed_api_key=..., schema_name="knowledge", table_name="kb_chunks")` for production
  - Methods match Retriever Port
  - Search errors → `[]` + log
  - Blank tenant → `ValueError`

- [ ] **Step 1: Write failing unit tests with a fake store**

```python
# packages/core/tests/adapters/test_langchain_pg_retriever.py
from __future__ import annotations

import logging

import pytest
from langchain_core.documents import Document

from agent_base_core.adapters.langchain_pg_retriever import LangchainPgRetriever


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
```

Note: `langchain_core.documents.Document` is already a core dependency via `langchain-core`. Do **not** import `langchain_postgres` in this test file.

- [ ] **Step 2: Run test — expect fail (module missing)**

Run: `python -m pytest packages/core/tests/adapters/test_langchain_pg_retriever.py -v`  
Expected: FAIL import error

- [ ] **Step 3: Implement adapter**

```python
# packages/core/src/agent_base_core/adapters/langchain_pg_retriever.py
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

        # TEI / OpenAI-compatible HTTP embeddings
        embeddings = OpenAIEmbeddings(
            model=embed_model,
            api_key=embed_api_key or "not-needed",
            base_url=embed_api_base.rstrip("/"),
            dimensions=embed_dimensions,
        )
        engine = PGEngine.from_connection_string(url=dsn)
        # Table must already exist (migration 003) with tenant_id column.
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
        # Best-effort; PGEngine API may vary by version — guard attributes.
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
```

If `PGVectorStore.create` / `DistanceStrategy` import paths differ in the pinned package version, adjust **only inside this file** to match the installed `langchain-postgres` docs — keep the public `LangchainPgRetriever` API stable.

Update `.importlinter` independence `modules=` list: append  
`agent_base_core.adapters.langchain_pg_retriever`  
and `agent_base_core.adapters.fake_retriever` if not already listed (fake may already be absent — only add new module; do not refactor unrelated adapters).

- [ ] **Step 4: Run unit tests**

Run: `python -m pytest packages/core/tests/adapters/test_langchain_pg_retriever.py packages/core/tests/adapters/test_retriever_memory.py -v`  
Expected: PASS (no pgvector required)

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/agent_base_core/adapters/langchain_pg_retriever.py packages/core/tests/adapters/test_langchain_pg_retriever.py .importlinter
git commit -m "feat(core): add LangchainPgRetriever with tenant filter and degrade-empty"
```

---

### Task 5: Settings + lifespan wiring + startup validation

**Files:**
- Modify: `apps/api/config/settings.py`
- Modify: `apps/api/lifespan.py`
- Create: `apps/api/tests/test_knowledge_backend_settings.py`

**Interfaces:**
- Consumes: `FakeRetriever`, `LangchainPgRetriever.create`
- Produces: `app.state.retriever` selected by `KNOWLEDGE_BACKEND`; `close()` on shutdown

- [ ] **Step 1: Write failing tests for settings resolution helper**

Prefer a small pure helper in lifespan (or `apps/api/adapters/knowledge_backend.py`) so tests do not boot full FastAPI:

```python
# apps/api/adapters/knowledge_backend.py
"""Build Retriever from Settings (composition helper)."""

from __future__ import annotations

from typing import Any

from agent_base_core.adapters.fake_retriever import FakeRetriever
from config.settings import Settings


def resolve_kb_dsn(settings: Settings) -> str:
    if settings.kb_dsn:
        return settings.kb_dsn
    if settings.pg_dsn:
        return settings.pg_dsn
    return (
        f"postgresql://{settings.pg_user}:{settings.pg_password}"
        f"@{settings.pg_host}:{settings.pg_port}/{settings.pg_database}"
    )


def validate_langchain_pg_settings(settings: Settings) -> None:
    missing: list[str] = []
    if not (settings.embed_api_base or "").strip():
        missing.append("EMBED_API_BASE")
    if not (settings.embed_model or "").strip():
        missing.append("EMBED_MODEL")
    if settings.embed_dimensions is None or int(settings.embed_dimensions) <= 0:
        missing.append("EMBED_DIMENSIONS")
    dsn = resolve_kb_dsn(settings)
    if not dsn.strip():
        missing.append("KB_DSN or PG_DSN")
    if missing:
        raise RuntimeError(
            "KNOWLEDGE_BACKEND=langchain_pg missing required config: "
            + ", ".join(missing)
        )


async def build_retriever(settings: Settings) -> Any:
    backend = (settings.knowledge_backend or "fake").strip().lower()
    if backend == "fake":
        return FakeRetriever()
    if backend == "langchain_pg":
        validate_langchain_pg_settings(settings)
        from agent_base_core.adapters.langchain_pg_retriever import LangchainPgRetriever

        return await LangchainPgRetriever.create(
            dsn=resolve_kb_dsn(settings),
            embed_api_base=settings.embed_api_base,
            embed_model=settings.embed_model,
            embed_dimensions=int(settings.embed_dimensions),
            embed_api_key=settings.embed_api_key or "",
        )
    raise RuntimeError(
        f"Unsupported KNOWLEDGE_BACKEND={backend!r}; use fake|langchain_pg"
    )
```

Test file:

```python
# apps/api/tests/test_knowledge_backend_settings.py
import pytest
from adapters.knowledge_backend import validate_langchain_pg_settings
from config.settings import Settings


def test_validate_langchain_pg_requires_embed() -> None:
    s = Settings(
        knowledge_backend="langchain_pg",
        pg_dsn="postgresql://u:p@localhost:5432/db",
        embed_api_base="",
        embed_model="m",
        embed_dimensions=1024,
    )
    with pytest.raises(RuntimeError, match="EMBED_API_BASE"):
        validate_langchain_pg_settings(s)


def test_validate_langchain_pg_ok() -> None:
    s = Settings(
        knowledge_backend="langchain_pg",
        pg_dsn="postgresql://u:p@localhost:5432/db",
        embed_api_base="http://127.0.0.1:8080/v1",
        embed_model="bge",
        embed_dimensions=1024,
    )
    validate_langchain_pg_settings(s)  # no raise
```

- [ ] **Step 2: Run test — expect fail until Settings fields exist**

Run: `python -m pytest apps/api/tests/test_knowledge_backend_settings.py -v`  
Expected: FAIL (unknown fields / import)

- [ ] **Step 3: Add Settings fields**

Append to `apps/api/config/settings.py` `Settings` class:

```python
    knowledge_backend: str = Field(default="fake", validation_alias="KNOWLEDGE_BACKEND")
    kb_dsn: str = Field(default="", validation_alias="KB_DSN")
    embed_api_base: str = Field(default="", validation_alias="EMBED_API_BASE")
    embed_model: str = Field(default="", validation_alias="EMBED_MODEL")
    embed_dimensions: int = Field(default=0, validation_alias="EMBED_DIMENSIONS")
    embed_api_key: str = Field(default="", validation_alias="EMBED_API_KEY")
```

Implement `apps/api/adapters/knowledge_backend.py` as in Step 1.

In `apps/api/lifespan.py`:
- Replace `retriever = FakeRetriever()` with `retriever = await build_retriever(settings)`
- Import `build_retriever` from `adapters.knowledge_backend`
- In `finally`, if `hasattr(retriever, "close")`, await close (same pattern as redis)

- [ ] **Step 4: Run api unit tests for settings + existing demo_rag still under Fake**

Run:

```bash
python -m pytest apps/api/tests/test_knowledge_backend_settings.py apps/api/tests/test_demo_rag.py -v
```

Expected: settings PASS; demo_rag may still fail until Task 6 (if citation assertions not updated yet, demo_rag may still PASS on type-only check)

- [ ] **Step 5: Commit**

```bash
git add apps/api/config/settings.py apps/api/adapters/knowledge_backend.py apps/api/lifespan.py apps/api/tests/test_knowledge_backend_settings.py
git commit -m "feat(api): wire KNOWLEDGE_BACKEND fake|langchain_pg in lifespan"
```

---

### Task 6: demo_rag citation alignment

**Files:**
- Modify: `apps/api/domains/demo_rag/graph.py`
- Modify: `apps/api/tests/test_demo_rag.py`

**Interfaces:**
- Consumes: retriever hits shaped as KnowledgeHit
- Produces: SSE `x.bridge.citation` with `chunk_id`/`doc_id`/`text`/`tenant_id`

- [ ] **Step 1: Strengthen failing assertions in test**

Update seed + asserts in `apps/api/tests/test_demo_rag.py`:

```python
    await fake.ingest(
        [{"chunk_id": "d1", "doc_id": "doc-1", "text": "refund policy 30 days"}],
        tenant_id="dev",
    )
    ...
    events = _parse_sse(r.text)
    cite = next(e for e in events if e["type"] == "x.bridge.citation")
    assert cite["data"]["route"] == "demo_rag"
    c0 = cite["data"]["citations"][0]
    assert c0["chunk_id"] == "d1"
    assert c0["doc_id"] == "doc-1"
    assert "refund" in c0["text"]
    assert c0["tenant_id"] == "dev"
```

Also fix graph if it still uses `ctx.tenant_id or "default"` — blank tenant should not be invented for Port calls; if context tenant is missing in tests, ensure test auth/context provides `dev` (match existing test behavior). Keep `k=3` in tool call.

- [ ] **Step 2: Run test — expect fail on citation fields**

Run: `python -m pytest apps/api/tests/test_demo_rag.py -v`  
Expected: FAIL missing chunk_id

- [ ] **Step 3: Update `_cite` in demo_rag**

```python
def _cite(state: DemoRagState) -> dict[str, Any]:
    citations: list[dict[str, Any]] = []
    for m in state.get("messages") or []:
        name = getattr(m, "name", None)
        if name == "search_knowledge":
            content = getattr(m, "content", None)
            if isinstance(content, list):
                for doc in content:
                    if isinstance(doc, dict):
                        citations.append(
                            {
                                "chunk_id": doc.get("chunk_id") or doc.get("id"),
                                "doc_id": doc.get("doc_id")
                                or doc.get("chunk_id")
                                or doc.get("id"),
                                "text": doc.get("text"),
                                "tenant_id": doc.get("tenant_id"),
                                **(
                                    {"score": doc["score"]}
                                    if "score" in doc
                                    else {}
                                ),
                            }
                        )
    return {
        OUTBOUND_EXTENSIONS_KEY: [
            {
                "type": "x.bridge.citation",
                "data": {"citations": citations, "route": "demo_rag"},
            }
        ]
    }
```

Do **not** import adapters or langchain_postgres in this domain file.

- [ ] **Step 4: Run test**

Run: `python -m pytest apps/api/tests/test_demo_rag.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/domains/demo_rag/graph.py apps/api/tests/test_demo_rag.py
git commit -m "feat(demo_rag): align citation payload with KnowledgeHit"
```

---

### Task 7: Architecture gates (domains cannot import engine SDKs)

**Files:**
- Create: `scripts/import_scan_domains_rag.py`
- Modify: `.github/workflows/ci.yml` (architecture-gates job)

**Interfaces:**
- Consumes: AST scan of `apps/api/domains`
- Produces: CI failure if domains import `langchain_postgres` / `langchain_openai` / `langchain_community`

- [ ] **Step 1: Write scanner + a tiny negative fixture check (optional unit via subprocess)**

```python
# scripts/import_scan_domains_rag.py
"""Fail if apps/api/domains imports knowledge engine SDKs."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FORBIDDEN_PREFIXES = (
    "langchain_postgres",
    "langchain_openai",
    "langchain_community",
)
DOMAINS = Path(__file__).resolve().parents[1] / "apps" / "api" / "domains"


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append((node.lineno, node.module))
    return found


def main() -> int:
    if not DOMAINS.is_dir():
        print(f"domains not found: {DOMAINS}", file=sys.stderr)
        return 1
    violations: list[str] = []
    for py in DOMAINS.rglob("*.py"):
        rel = py.relative_to(DOMAINS.parents[2])
        for lineno, mod in _imports(py):
            for bad in FORBIDDEN_PREFIXES:
                if mod == bad or mod.startswith(f"{bad}."):
                    violations.append(f"{rel}:{lineno} imports {mod!r}")
    if violations:
        print("Forbidden engine imports in domains:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print("import_scan_domains_rag: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run scanner**

Run: `python scripts/import_scan_domains_rag.py`  
Expected: `import_scan_domains_rag: OK`

- [ ] **Step 3: Wire CI**

In `.github/workflows/ci.yml` under `architecture-gates` steps, after `import_scan_core.py`:

```yaml
      - name: Scan domains for forbidden RAG engine imports
        run: python scripts/import_scan_domains_rag.py
```

- [ ] **Step 4: Commit**

```bash
git add scripts/import_scan_domains_rag.py .github/workflows/ci.yml
git commit -m "ci: forbid knowledge engine imports inside domains"
```

---

### Task 8: Migration, seed script, docs, R-A checklist

**Files:**
- Create: `apps/api/migrations/003_knowledge_pgvector.sql`
- Modify: `apps/api/migrations/README.md`
- Modify: `scripts/ingest_demo_rag.py`
- Modify: `.env.example`
- Modify: `docs/knowledge-base.md`
- Modify: `docs/deploy.md`
- Modify: `docs/superpowers/plans/2026-07-27-plan6-rag-production.md` (link R-A detailed plan; mark T1–T8 checklist pointers)
- Modify: `docs/superpowers/specs/2026-07-27-platform-ra-design.md` (point **实施计划** to this file; status → 实施中/计划已就绪)

**Interfaces:**
- Consumes: Fake / langchain_pg Port
- Produces: operable hand-test path with TEI

- [ ] **Step 1: Add migration SQL**

```sql
-- apps/api/migrations/003_knowledge_pgvector.sql
-- R-A: knowledge schema + table for langchain_pg (filterable tenant_id column).
-- Idempotent. Requires pgvector extension (pgvector/pgvector:pg16 image).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS knowledge;

-- Column set aligned with LangchainPgRetriever.create metadata_columns.
-- embedding vector size must match EMBED_DIMENSIONS at runtime; default 1024.
-- If your TEI model uses another size, adjust before first ingest OR recreate table.
CREATE TABLE IF NOT EXISTS knowledge.kb_chunks (
    langchain_id UUID PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1024),
    tenant_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    langchain_metadata JSONB
);

CREATE INDEX IF NOT EXISTS kb_chunks_tenant_id_idx
    ON knowledge.kb_chunks (tenant_id);
```

Document in `migrations/README.md`: apply with existing migration runner; for RAG profile use pgvector image; **vector dimensions must match `EMBED_DIMENSIONS`**.

If `langchain-postgres` expects different default column names for your pinned version, adjust SQL **and** `LangchainPgRetriever.create(...)` together in the same commit.

- [ ] **Step 2: Update seed script**

```python
# scripts/ingest_demo_rag.py — use KnowledgeHit fields; still defaults to Fake offline
...
    n = await r.ingest(
        [
            {
                "chunk_id": "d1",
                "doc_id": "doc-refund",
                "text": "refund policy allows 30 days",
            },
            {
                "chunk_id": "d2",
                "doc_id": "doc-ship",
                "text": "shipping takes 5 days",
            },
        ],
        tenant_id="acme",
    )
    hits = await r.similarity_search("refund policy", tenant_id="acme", k=5)
    ...
    assert hits[0]["chunk_id"] == "d1"
```

Add a short module docstring note: for `langchain_pg`, run against a live API process / write a small async main that builds retriever via settings (optional follow-up); Fake path remains the default offline smoke.

- [ ] **Step 3: Docs + env**

`.env.example` append:

```env
# Knowledge backend (R-A)
# KNOWLEDGE_BACKEND=fake|langchain_pg
KNOWLEDGE_BACKEND=fake
# KB_DSN=                 # optional; falls back to PG_DSN
# EMBED_API_BASE=http://127.0.0.1:8080/v1
# EMBED_MODEL=your-tei-model
# EMBED_DIMENSIONS=1024
# EMBED_API_KEY=
```

`docs/knowledge-base.md`:
- Say current Port method is `similarity_search` (not `search`)
- R-A: `langchain_pg` + local TEI; install `pip install -e "apps/api[rag]"`
- Hand-test steps from design §7.2
- Note HTTP `/ingest` is R-B

`docs/deploy.md`: confirm `rag` extra name and compose `--profile rag`

Update Plan6 header to link: **Detailed R-A plan:** `./2026-07-27-platform-ra.md`

- [ ] **Step 4: Run full default CI-equivalent suite**

```bash
lint-imports
python scripts/import_scan_core.py
python scripts/import_scan_domains_rag.py
python -m pytest packages/core/tests apps/api/tests -q
```

Expected: all green

- [ ] **Step 5: Manual R-A acceptance (operator checklist — not CI)**

1. `docker compose --profile rag up -d`
2. Apply `003_knowledge_pgvector.sql` (dimensions match TEI)
3. `pip install -e "apps/api[rag]"`
4. `.env`: `KNOWLEDGE_BACKEND=langchain_pg`, `EMBED_*` → local TEI, DSN → rag postgres
5. Seed via temporary Python calling `build_retriever` + `ingest`, or extended script
6. `POST /chat/stream` route `demo_rag` → citations; second tenant sees nothing

- [ ] **Step 6: Commit**

```bash
git add apps/api/migrations/003_knowledge_pgvector.sql apps/api/migrations/README.md scripts/ingest_demo_rag.py .env.example docs/knowledge-base.md docs/deploy.md docs/superpowers/plans/2026-07-27-plan6-rag-production.md docs/superpowers/specs/2026-07-27-platform-ra-design.md
git commit -m "docs: R-A migration, seed script, and knowledge ops notes"
```

---

## Spec coverage self-check

| Spec requirement | Task |
|------------------|------|
| `KnowledgeHit` TypedDict | T1 |
| Port `similarity_search` / `ingest`, `k=5` | T1–T2 |
| Fake aligned + blank tenant raises | T2 |
| `rag` extra only | T3 |
| `LangchainPgRetriever` + TEI HTTP + single collection + tenant column filter | T4 |
| Search degrade to `[]` | T4 |
| `KNOWLEDGE_BACKEND` lifespan + startup validation | T5 |
| `demo_rag` citation + `data.route` | T6 |
| Domains forbid engine imports | T7 |
| Migration / seed / docs / hand-test | T8 |
| No HTTP `/ingest`, no hybrid, no external/product | Out of scope (explicit) |

## Placeholder / consistency scan

- No TBD steps; TEI base path documented as OpenAI-compatible (`EMBED_API_BASE` ending such that client hits `/v1/embeddings` — if TEI serves at root, set base accordingly in `.env`, same as RAG_Agent).
- Types: `KnowledgeHit`, `LangchainPgRetriever`, `build_retriever` names stable across tasks.
- If `langchain-postgres` API differs at install time, only Task 4/8 adapter+SQL may adjust; Port stays fixed.
