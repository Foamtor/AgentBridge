"""KnowledgeHit normalize helpers."""

from __future__ import annotations

import pytest
from agent_base_core.protocol.knowledge import (
    doc_to_knowledge_hit,
    normalize_ingest_doc,
    require_tenant_id,
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
