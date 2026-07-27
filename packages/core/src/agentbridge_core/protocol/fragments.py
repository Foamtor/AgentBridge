"""Semantic outbound payload before RunLifecycle assigns envelope fields."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

OUTBOUND_EXTENSIONS_KEY = "outbound_extensions"


class OutboundFragment(BaseModel):
    """Protocol-layer fragment: type + data only (no run_id/sequence/event_id).

    Adapters and domain state may produce this model. Application layer
    (RunLifecycle) converts it to a contracts envelope via build_event or
    build_extension_event. Must live under protocol/, not adapters/application.
    """

    model_config = ConfigDict(extra="forbid")

    type: str
    data: dict[str, Any] = Field(default_factory=dict)
    step: str | None = None
    status: str | None = None
