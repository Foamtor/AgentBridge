"""RunContext and checkpoint thread key helpers."""

from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, Field

RUN_CONTEXT_KEY = "run_context"


class RunContext(BaseModel):
    user_id: str = ""
    tenant_id: str = ""
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    max_tokens: int | None = None
    max_tool_calls: int | None = None
    deadline_ms: int | None = None
    run_id: str = ""
    trace_id: str = ""
    parent_run_id: str = ""
    agent_id: str = ""
    policy_bundle_version: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


def get_run_context(config: Mapping[str, Any] | None) -> RunContext:
    if not config:
        return RunContext()
    raw = (config.get("configurable") or {}).get(RUN_CONTEXT_KEY)
    if raw is None:
        return RunContext()
    if isinstance(raw, RunContext):
        return raw
    return RunContext.model_validate(raw)


def checkpoint_thread_key(tenant_id: str, thread_id: str) -> str:
    return f"{tenant_id}::{thread_id}"
