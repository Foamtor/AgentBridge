"""HTTP DTOs for chat."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatStreamRequest(BaseModel):
    query: str
    thread_id: str
    route: str
    model: str = "default"
    extra: dict[str, Any] = Field(default_factory=dict)


class CancelRequest(BaseModel):
    thread_id: str
    run_id: str | None = None
