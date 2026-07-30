"""Read-only RAG-Agent PostgreSQL retriever tests."""

from __future__ import annotations

from types import TracebackType
from typing import Any, NoReturn, Self

import pytest
from adapters.rag_agent_pg_retriever import RagAgentPgRetriever
from agentbridge_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agentbridge_core.adapters.inprocess_lock import InProcessThreadLock
from agentbridge_core.adapters.noop_hooks import NoopHooks
from agentbridge_core.application.run_lifecycle import RunLifecycle
from agentbridge_core.errors import KnowledgeBackendUnavailable
from agentbridge_core.protocol.context import RunContext
from agentbridge_core.registry.graphs import GraphRegistry
from agentbridge_core.registry.input_builders import InputBuilderRegistry
from agentbridge_core.registry.tools import ToolRegistry

PUBLIC_ERROR = "knowledge backend unavailable"


class FailOnUse:
    def __getattr__(self, name: str) -> NoReturn:
        raise AssertionError(f"external dependency used: {name}")


class FakeResponse:
    def __init__(
        self,
        payload: Any,
        *,
        failure: Exception | None = None,
    ) -> None:
        self._payload = payload
        self._failure = failure

    def raise_for_status(self) -> None:
        if self._failure is not None:
            raise self._failure

    def json(self) -> Any:
        return self._payload


class RecordingEmbeddingClient:
    def __init__(
        self,
        payload: Any,
        *,
        failure: Exception | None = None,
    ) -> None:
        self._response = FakeResponse(payload, failure=failure)
        self.posts: list[dict[str, Any]] = []
        self.close_calls = 0

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> FakeResponse:
        self.posts.append({"url": url, "json": json, "headers": headers})
        return self._response

    async def aclose(self) -> None:
        self.close_calls += 1


class RecordingTransaction:
    def __init__(
        self,
        connection: RecordingConnection,
        kwargs: dict[str, Any],
    ) -> None:
        self._connection = connection
        self._kwargs = kwargs

    async def __aenter__(self) -> Self:
        self._connection.transaction_calls.append(self._kwargs)
        self._connection.transaction_kwargs = self._kwargs
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class RecordingConnection:
    def __init__(
        self,
        *,
        extversion: str | None = "0.8.2",
        tables: tuple[str | None, str | None, str | None] = (
            "kb_document",
            "kb_section",
            "kb_chunk",
        ),
        embedding_type: str | None = "vector(512)",
        rows: list[dict[str, Any]] | None = None,
        query_failure: Exception | None = None,
    ) -> None:
        self.extversion = extversion
        self.tables = tables
        self.embedding_type = embedding_type
        self.rows = rows or []
        self.query_failure = query_failure
        self.transaction_calls: list[dict[str, Any]] = []
        self.transaction_kwargs: dict[str, Any] = {}
        self.probe_sql: list[str] = []
        self.sql = ""
        self.query_args: tuple[Any, ...] = ()

    def transaction(self, **kwargs: Any) -> RecordingTransaction:
        return RecordingTransaction(self, kwargs)

    async def fetchval(self, sql: str) -> str | None:
        self.probe_sql.append(sql)
        if "pg_extension" in sql:
            return self.extversion
        if "pg_attribute" in sql:
            return self.embedding_type
        raise AssertionError(f"unexpected fetchval SQL: {sql}")

    async def fetchrow(
        self, sql: str
    ) -> tuple[str | None, str | None, str | None]:
        self.probe_sql.append(sql)
        if "to_regclass" not in sql:
            raise AssertionError(f"unexpected fetchrow SQL: {sql}")
        return self.tables

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        self.sql = sql
        self.query_args = args
        if self.query_failure is not None:
            raise self.query_failure
        return self.rows


class AcquireConnection:
    def __init__(self, connection: RecordingConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> RecordingConnection:
        return self._connection

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class RecordingPool:
    def __init__(self, connection: RecordingConnection) -> None:
        self.connection = connection
        self.acquire_calls = 0
        self.close_calls = 0

    def acquire(self) -> AcquireConnection:
        self.acquire_calls += 1
        return AcquireConnection(self.connection)

    async def close(self) -> None:
        self.close_calls += 1


class FakeCheckpointerFactory:
    async def get(self) -> None:
        return None


class CapturingSink:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def emit(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    async def close(self) -> None:
        return None


class RetrieverRuntime:
    def __init__(self, retriever: RagAgentPgRetriever) -> None:
        self._retriever = retriever

    async def astream(self, builder: Any, **kwargs: Any):
        await self._retriever.similarity_search(
            kwargs["query"],
            tenant_id=kwargs["extra"]["run_context"].tenant_id,
        )
        if False:
            yield  # pragma: no cover


def embedding_payload(dimensions: int = 512) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "object": "embedding",
                "index": 0,
                "embedding": [0.125] * dimensions,
            }
        ],
        "model": "BAAI/bge-m3",
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }


def build_retriever(
    *,
    connection: RecordingConnection | None = None,
    client: Any | None = None,
    owns_pool: bool = False,
    owns_client: bool = False,
) -> tuple[RagAgentPgRetriever, RecordingPool]:
    pool = RecordingPool(connection or RecordingConnection())
    retriever = RagAgentPgRetriever(
        dsn="postgresql://unused",
        demo_tenant="rag-agent-demo",
        embed_api_base="http://embed.test/v1/",
        embed_api_key="EMPTY",
        embed_model="BAAI/bge-m3",
        embed_dimensions=512,
        pool=pool,
        client=client or RecordingEmbeddingClient(embedding_payload()),
        owns_pool=owns_pool,
        owns_client=owns_client,
    )
    return retriever, pool


async def lifecycle_events(retriever: RagAgentPgRetriever) -> list[dict[str, Any]]:
    graphs = GraphRegistry()
    graphs.register("echo", lambda **kwargs: object())
    tools = ToolRegistry()
    tools.register("echo", [])
    lifecycle = RunLifecycle(
        locks=InProcessThreadLock(),
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=RetrieverRuntime(retriever),
        cancels=InProcessCancelRegistry(),
        hooks=NoopHooks(),
    )
    sink = CapturingSink()
    await lifecycle.start_stream(
        query="policy",
        thread_id="rag-agent-failure",
        route="echo",
        sink=sink,
        ctx=RunContext(tenant_id="rag-agent-demo"),
    )
    return sink.events


@pytest.mark.asyncio
async def test_non_demo_tenant_returns_empty_without_external_io() -> None:
    retriever = RagAgentPgRetriever(
        dsn="unused",
        demo_tenant="rag-agent-demo",
        embed_api_base="http://unused/v1",
        embed_api_key="EMPTY",
        embed_model="BAAI/bge-m3",
        embed_dimensions=512,
        pool=FailOnUse(),
        client=FailOnUse(),
    )

    assert (
        await retriever.similarity_search("policy", tenant_id="other", k=3)
        == []
    )


@pytest.mark.asyncio
async def test_similarity_search_maps_citations_in_readonly_transaction() -> None:
    connection = RecordingConnection(
        rows=[
            {
                "chunk_id": "chunk-1",
                "doc_id": "doc-1",
                "text": "policy text",
                "title": "Policy",
                "section_id": "s1",
                "heading": "Scope",
                "score": 0.8,
            }
        ]
    )
    client = RecordingEmbeddingClient(embedding_payload())
    retriever, _ = build_retriever(connection=connection, client=client)

    hits = await retriever.similarity_search(
        "policy",
        tenant_id="rag-agent-demo",
        k=3,
    )

    assert connection.transaction_kwargs["readonly"] is True
    assert "kb_document" in connection.sql
    assert "kb_section" in connection.sql
    assert "kb_chunk" in connection.sql
    assert "$1::vector" in connection.sql
    assert not any(
        keyword in connection.sql.upper()
        for keyword in ("INSERT ", "UPDATE ", "DELETE ", "CREATE ", "ALTER ", "DROP ")
    )
    assert connection.query_args[1] == 3
    assert client.posts == [
        {
            "url": "http://embed.test/v1/embeddings",
            "json": {"model": "BAAI/bge-m3", "input": ["policy"]},
            "headers": {"Authorization": "Bearer EMPTY"},
        }
    ]
    assert hits == [
        {
            "chunk_id": "chunk-1",
            "doc_id": "doc-1",
            "text": "policy text",
            "tenant_id": "rag-agent-demo",
            "score": pytest.approx(0.8),
            "metadata": {
                "title": "Policy",
                "section_id": "s1",
                "heading": "Scope",
                "source_backend": "rag_agent_pg",
            },
        }
    ]


@pytest.mark.asyncio
async def test_similarity_search_clamps_scores_to_unit_interval() -> None:
    connection = RecordingConnection(
        rows=[
            {
                "chunk_id": "high",
                "doc_id": "doc-1",
                "text": "high score",
                "title": "Policy",
                "section_id": "s1",
                "heading": "Scope",
                "score": 1.25,
            },
            {
                "chunk_id": "low",
                "doc_id": "doc-1",
                "text": "low score",
                "title": "Policy",
                "section_id": "s2",
                "heading": "Other",
                "score": -0.25,
            },
        ]
    )
    retriever, _ = build_retriever(connection=connection)

    hits = await retriever.similarity_search(
        "policy",
        tenant_id="rag-agent-demo",
    )

    assert [hit["score"] for hit in hits] == [1.0, 0.0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("extversion", "tables", "embedding_type"),
    [
        (
            None,
            ("kb_document", "kb_section", "kb_chunk"),
            "vector(512)",
        ),
        (
            "0.8.2",
            (None, "kb_section", "kb_chunk"),
            "vector(512)",
        ),
        (
            "0.8.2",
            ("kb_document", None, "kb_chunk"),
            "vector(512)",
        ),
        (
            "0.8.2",
            ("kb_document", "kb_section", None),
            "vector(512)",
        ),
        (
            "0.8.2",
            ("kb_document", "kb_section", "kb_chunk"),
            "vector(1024)",
        ),
    ],
    ids=[
        "vector-extension-missing",
        "document-table-missing",
        "section-table-missing",
        "chunk-table-missing",
        "embedding-type-mismatch",
    ],
)
async def test_create_rejects_missing_schema_capabilities_safely(
    extversion: str | None,
    tables: tuple[str | None, str | None, str | None],
    embedding_type: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_dsn = "postgresql://admin:dsn-secret@db/rag"
    api_key = "embed-api-secret"
    connection = RecordingConnection(
        extversion=extversion,
        tables=tables,
        embedding_type=embedding_type,
    )
    pool = RecordingPool(connection)
    client = RecordingEmbeddingClient(embedding_payload())

    with pytest.raises(KnowledgeBackendUnavailable) as captured:
        await RagAgentPgRetriever.create(
            dsn=secret_dsn,
            demo_tenant="rag-agent-demo",
            embed_api_base="http://embed.test/v1",
            embed_api_key=api_key,
            embed_model="BAAI/bge-m3",
            embed_dimensions=512,
            pool=pool,
            client=client,
        )

    assert str(captured.value) == PUBLIC_ERROR
    assert all(call["readonly"] is True for call in connection.transaction_calls)
    assert secret_dsn not in caplog.text
    assert api_key not in caplog.text


@pytest.mark.asyncio
async def test_create_rejects_wrong_embedding_dimension_safely(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_dsn = "postgresql://admin:dsn-secret@db/rag"
    api_key = "embed-api-secret"
    connection = RecordingConnection()
    pool = RecordingPool(connection)
    client = RecordingEmbeddingClient(embedding_payload(511))

    with pytest.raises(KnowledgeBackendUnavailable) as captured:
        await RagAgentPgRetriever.create(
            dsn=secret_dsn,
            demo_tenant="rag-agent-demo",
            embed_api_base="http://embed.test/v1",
            embed_api_key=api_key,
            embed_model="BAAI/bge-m3",
            embed_dimensions=512,
            pool=pool,
            client=client,
        )

    assert str(captured.value) == PUBLIC_ERROR
    assert secret_dsn not in caplog.text
    assert api_key not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"data": []},
        {"data": [{}]},
        {"data": [{"embedding": "not-a-vector"}]},
        {"data": [{"embedding": [0.125] * 511 + ["bad"]}]},
    ],
    ids=[
        "body-not-object",
        "missing-data",
        "empty-data",
        "missing-embedding",
        "embedding-not-list",
        "embedding-not-numeric",
    ],
)
async def test_similarity_search_rejects_malformed_embedding_payload(
    payload: Any,
) -> None:
    retriever, pool = build_retriever(
        client=RecordingEmbeddingClient(payload),
    )

    with pytest.raises(KnowledgeBackendUnavailable) as captured:
        await retriever.similarity_search(
            "policy",
            tenant_id="rag-agent-demo",
        )

    assert str(captured.value) == PUBLIC_ERROR
    assert pool.acquire_calls == 0


@pytest.mark.asyncio
async def test_health_check_repeats_readonly_dependency_probes() -> None:
    connection = RecordingConnection()
    pool = RecordingPool(connection)
    client = RecordingEmbeddingClient(embedding_payload())
    retriever = await RagAgentPgRetriever.create(
        dsn="postgresql://unused",
        demo_tenant="rag-agent-demo",
        embed_api_base="http://embed.test/v1",
        embed_api_key="EMPTY",
        embed_model="BAAI/bge-m3",
        embed_dimensions=512,
        pool=pool,
        client=client,
    )

    health = await retriever.health_check()

    assert health == {"status": "ok", "backend": "rag_agent_pg"}
    assert connection.transaction_calls == [
        {"readonly": True},
        {"readonly": True},
    ]
    probe_sql = "\n".join(connection.probe_sql)
    assert "extname = 'vector'" in probe_sql
    assert "to_regclass('public.kb_document')" in probe_sql
    assert "to_regclass('public.kb_section')" in probe_sql
    assert "to_regclass('public.kb_chunk')" in probe_sql
    assert "attrelid = 'kb_chunk'::regclass" in probe_sql
    assert len(client.posts) == 2


@pytest.mark.asyncio
async def test_close_leaves_injected_resources_caller_owned() -> None:
    connection = RecordingConnection()
    pool = RecordingPool(connection)
    client = RecordingEmbeddingClient(embedding_payload())
    retriever = await RagAgentPgRetriever.create(
        dsn="postgresql://unused",
        demo_tenant="rag-agent-demo",
        embed_api_base="http://embed.test/v1",
        embed_api_key="EMPTY",
        embed_model="BAAI/bge-m3",
        embed_dimensions=512,
        pool=pool,
        client=client,
    )

    await retriever.close()

    assert pool.close_calls == 0
    assert client.close_calls == 0


@pytest.mark.asyncio
async def test_close_closes_owned_resources_once() -> None:
    client = RecordingEmbeddingClient(embedding_payload())
    retriever, pool = build_retriever(
        client=client,
        owns_pool=True,
        owns_client=True,
    )

    await retriever.close()
    await retriever.close()

    assert pool.close_calls == 1
    assert client.close_calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_stage", ["embedding", "database"])
async def test_runtime_failures_map_through_lifecycle_without_secrets(
    failure_stage: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "postgresql://admin:runtime-secret@db/private"
    if failure_stage == "embedding":
        client = RecordingEmbeddingClient(
            embedding_payload(),
            failure=RuntimeError(f"embedding failed {secret}"),
        )
        connection = RecordingConnection()
    else:
        client = RecordingEmbeddingClient(embedding_payload())
        connection = RecordingConnection(
            query_failure=RuntimeError(f"database failed {secret}")
        )
    retriever, _ = build_retriever(connection=connection, client=client)

    events = await lifecycle_events(retriever)

    error = next(event for event in events if event["type"] == "error")
    assert error["data"] == {
        "code": "knowledge_backend_unavailable",
        "message": PUBLIC_ERROR,
    }
    assert secret not in str(events)
    assert secret not in caplog.text
