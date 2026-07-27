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
