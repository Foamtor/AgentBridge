"""POST /ingest — knowledge document ingest (R-B)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from routes.admin_common import admin_ctx

router = APIRouter(tags=["knowledge"])


class IngestDocBody(BaseModel):
    text: str
    chunk_id: str | None = None
    id: str | None = None
    doc_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_doc(self) -> dict[str, Any]:
        doc: dict[str, Any] = {"text": self.text, "metadata": self.metadata}
        if self.chunk_id is not None:
            doc["chunk_id"] = self.chunk_id
        if self.id is not None:
            doc["id"] = self.id
        if self.doc_id is not None:
            doc["doc_id"] = self.doc_id
        return doc


class IngestRequest(BaseModel):
    docs: list[IngestDocBody]


def _require_ingest_write(ctx) -> None:
    if "*" in ctx.permissions or "knowledge:write" in ctx.permissions:
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "forbidden",
            "message": "missing knowledge:write",
        },
    )


@router.post("/ingest")
async def ingest_documents(body: IngestRequest, request: Request) -> dict[str, Any]:
    ctx = admin_ctx(request)
    _require_ingest_write(ctx)
    ingest = getattr(request.app.state, "knowledge_ingest", None)
    if ingest is None or not ingest.supports_ingest():
        raise HTTPException(
            status_code=501,
            detail={
                "code": "unsupported",
                "message": "knowledge ingest is not supported for this backend",
            },
        )
    if not body.docs:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_request", "message": "docs must not be empty"},
        )
    tenant_id = ctx.tenant_id or "default"
    docs = [d.to_doc() for d in body.docs]
    try:
        result = await ingest.ingest_documents(docs, tenant_id=tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_doc", "message": str(exc)},
        ) from exc
    audit = getattr(request.app.state, "audit", None)
    if audit is not None:
        await audit.log(
            user_id=ctx.user_id or "",
            tenant_id=tenant_id,
            action="ingest",
            resource="knowledge",
            detail={"job_id": result.get("job_id"), "doc_count": len(docs)},
            result="ok",
        )
    return result
