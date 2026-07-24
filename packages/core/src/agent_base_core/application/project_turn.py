"""Project a completed turn from EventLog into MessageStore + RunStore."""

from __future__ import annotations

from typing import Any

from agent_base_core.ports.event_log import EventLog
from agent_base_core.ports.message_store import MessageStore
from agent_base_core.ports.run_store import RunStore


def _merge_text_deltas(events: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for evt in events:
        if evt.get("type") != "text_delta":
            continue
        data = evt.get("data") or {}
        content = data.get("content")
        if content is None:
            content = data.get("text")
        if content is not None:
            parts.append(str(content))
    return "".join(parts)


def _tool_trace(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for evt in events:
        t = evt.get("type")
        if t in {"tool_call", "tool_result"}:
            out.append({"type": t, "data": dict(evt.get("data") or {})})
    return out


async def project_turn(
    *,
    event_log: EventLog,
    message_store: MessageStore,
    run_store: RunStore,
    tenant_id: str,
    thread_id: str,
    run_id: str,
    query: str,
    terminal: str,
) -> None:
    events = await event_log.list(run_id)
    await message_store.append_message(
        tenant_id,
        thread_id,
        {"role": "user", "content": query, "run_id": run_id},
    )
    assistant: dict[str, Any] = {
        "role": "assistant",
        "content": _merge_text_deltas(events),
        "run_id": run_id,
    }
    trace = _tool_trace(events)
    if trace:
        assistant["tool_trace"] = trace
    await message_store.append_message(tenant_id, thread_id, assistant)
    await run_store.upsert(
        {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "thread_id": thread_id,
            "status": terminal,
        }
    )
