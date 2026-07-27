"""Knowledge backend settings validation."""

from __future__ import annotations

import pytest
from adapters.knowledge_backend import validate_langchain_pg_settings
from config.settings import Settings


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
