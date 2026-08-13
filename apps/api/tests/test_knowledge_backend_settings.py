"""Knowledge backend settings validation."""

from __future__ import annotations

import pytest
from adapters.knowledge_backend import (
    build_retriever,
    validate_external_settings,
    validate_langchain_pg_settings,
    validate_rag_agent_pg_settings,
)
from adapters.knowledge_ingest_factory import build_knowledge_ingest
from agentbridge_core.adapters.memory_ingest_job_store import MemoryIngestJobStore
from agentbridge_core.adapters.unsupported_knowledge_ingest import (
    UnsupportedKnowledgeIngest,
)
from config.settings import Settings


def test_production_ingest_job_store_is_postgres() -> None:
    from adapters.postgres_ingest_job_store import PostgresIngestJobStore
    from lifespan import _build_ingest_job_store

    settings = Settings(
        _env_file=None,
        AGENTBRIDGE_FAKE_RUNTIME=False,
        PG_DSN="postgresql://u:p@db/agentbridge",
    )

    store = _build_ingest_job_store(settings)

    assert isinstance(store, PostgresIngestJobStore)


def test_validate_langchain_pg_requires_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PG_DSN", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("KNOWLEDGE_BACKEND", "langchain_pg")
    monkeypatch.setenv("EMBED_API_BASE", "")
    monkeypatch.setenv("EMBED_MODEL", "m")
    monkeypatch.setenv("EMBED_DIMENSIONS", "1024")
    s = Settings(_env_file=None)
    with pytest.raises(RuntimeError, match="EMBED_API_BASE"):
        validate_langchain_pg_settings(s)


def test_validate_langchain_pg_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PG_DSN", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("KNOWLEDGE_BACKEND", "langchain_pg")
    monkeypatch.setenv("EMBED_API_BASE", "http://127.0.0.1:8080/v1")
    monkeypatch.setenv("EMBED_MODEL", "bge")
    monkeypatch.setenv("EMBED_DIMENSIONS", "1024")
    s = Settings(_env_file=None)
    validate_langchain_pg_settings(s)


def test_validate_external_requires_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KNOWLEDGE_BACKEND", "external")
    monkeypatch.setenv("KB_EXTERNAL_BASE_URL", "")
    s = Settings(_env_file=None)
    with pytest.raises(RuntimeError, match="KB_EXTERNAL_BASE_URL"):
        validate_external_settings(s)


def rag_agent_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "KNOWLEDGE_BACKEND": "rag_agent_pg",
        "RAG_AGENT_PG_DSN": "postgresql://readonly@db/rag",
        "RAG_AGENT_DEMO_TENANT": "rag-agent-demo",
        "RAG_AGENT_EMBED_API_BASE": "http://127.0.0.1:8080/v1",
        "RAG_AGENT_EMBED_API_KEY": "EMPTY",
        "RAG_AGENT_EMBED_MODEL": "BAAI/bge-m3",
        "RAG_AGENT_EMBED_DIMENSIONS": 512,
    }
    values.update(overrides)
    return Settings(**values)


def test_rag_agent_pg_settings_have_safe_demo_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "RAG_AGENT_PG_DSN",
        "RAG_AGENT_DEMO_TENANT",
        "RAG_AGENT_EMBED_API_BASE",
        "RAG_AGENT_EMBED_API_KEY",
        "RAG_AGENT_EMBED_MODEL",
        "RAG_AGENT_EMBED_DIMENSIONS",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.rag_agent_pg_dsn == ""
    assert settings.rag_agent_demo_tenant == "rag-agent-demo"
    assert settings.rag_agent_embed_api_base == "http://127.0.0.1:8080/v1"
    assert settings.rag_agent_embed_api_key == "EMPTY"
    assert settings.rag_agent_embed_model == "BAAI/bge-m3"
    assert settings.rag_agent_embed_dimensions == 512


@pytest.mark.parametrize(
    ("override", "expected_name"),
    [
        ({"RAG_AGENT_PG_DSN": ""}, "RAG_AGENT_PG_DSN"),
        ({"RAG_AGENT_DEMO_TENANT": "  "}, "RAG_AGENT_DEMO_TENANT"),
        ({"RAG_AGENT_EMBED_API_BASE": ""}, "RAG_AGENT_EMBED_API_BASE"),
        ({"RAG_AGENT_EMBED_MODEL": ""}, "RAG_AGENT_EMBED_MODEL"),
        ({"RAG_AGENT_EMBED_MODEL": "other-512-model"}, "RAG_AGENT_EMBED_MODEL"),
        ({"RAG_AGENT_EMBED_DIMENSIONS": 0}, "RAG_AGENT_EMBED_DIMENSIONS"),
        ({"RAG_AGENT_EMBED_DIMENSIONS": -1}, "RAG_AGENT_EMBED_DIMENSIONS"),
        ({"RAG_AGENT_EMBED_DIMENSIONS": 1024}, "RAG_AGENT_EMBED_DIMENSIONS"),
    ],
)
def test_validate_rag_agent_pg_requires_complete_positive_settings(
    override: dict[str, object],
    expected_name: str,
) -> None:
    settings = rag_agent_settings(**override)

    with pytest.raises(RuntimeError, match=expected_name):
        validate_rag_agent_pg_settings(settings)


def test_validate_rag_agent_pg_accepts_complete_settings() -> None:
    validate_rag_agent_pg_settings(rag_agent_settings())


@pytest.mark.asyncio
async def test_build_retriever_rejects_wrong_rag_agent_model_before_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from adapters import rag_agent_pg_retriever as adapter_module

    class FailOnCreate:
        @classmethod
        async def create(cls, **kwargs: object) -> object:
            raise AssertionError("adapter create must not be called")

    monkeypatch.setattr(
        adapter_module,
        "RagAgentPgRetriever",
        FailOnCreate,
    )

    with pytest.raises(RuntimeError, match="RAG_AGENT_EMBED_MODEL"):
        await build_retriever(
            rag_agent_settings(
                RAG_AGENT_EMBED_MODEL="other-512-model",
            )
        )


@pytest.mark.asyncio
async def test_build_retriever_wires_only_rag_agent_pg_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from adapters import rag_agent_pg_retriever as adapter_module

    sentinel = object()
    calls: list[dict[str, object]] = []

    class RecordingRetriever:
        @classmethod
        async def create(cls, **kwargs: object) -> object:
            calls.append(kwargs)
            return sentinel

    monkeypatch.setattr(
        adapter_module,
        "RagAgentPgRetriever",
        RecordingRetriever,
    )
    settings = rag_agent_settings(
        RAG_AGENT_PG_DSN=" postgresql://readonly@db/rag ",
        RAG_AGENT_DEMO_TENANT=" rag-agent-demo ",
        RAG_AGENT_EMBED_API_BASE=" http://embed.test/v1/ ",
        RAG_AGENT_EMBED_MODEL=" BAAI/bge-m3 ",
    )

    retriever = await build_retriever(settings)

    assert retriever is sentinel
    assert calls == [
        {
            "dsn": "postgresql://readonly@db/rag",
            "demo_tenant": "rag-agent-demo",
            "embed_api_base": "http://embed.test/v1/",
            "embed_api_key": "EMPTY",
            "embed_model": "BAAI/bge-m3",
            "embed_dimensions": 512,
        }
    ]


@pytest.mark.asyncio
async def test_rag_agent_pg_ingest_is_explicitly_unsupported() -> None:
    ingest = build_knowledge_ingest(
        rag_agent_settings(),
        retriever=object(),
        job_store=MemoryIngestJobStore(),
    )

    assert isinstance(ingest, UnsupportedKnowledgeIngest)
    assert ingest.supports_ingest() is False
    with pytest.raises(
        NotImplementedError,
        match="ingest unsupported for backend 'rag_agent_pg'",
    ):
        await ingest.ingest_documents(
            [{"chunk_id": "x", "text": "not written"}],
            tenant_id="rag-agent-demo",
        )
