"""Platform-neutral projections derived from committed run events."""

from __future__ import annotations

from collections import Counter
from typing import Any

TERMINAL_TYPES = {"done", "error", "cancelled"}


def _timestamp(event: dict[str, Any]) -> int | None:
    value = event.get("timestamp")
    return value if isinstance(value, int | float) else None


def _assertion(key: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"key": key, "passed": passed, "detail": detail}


def build_run_diagnostics(events: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(events, key=lambda event: int(event.get("sequence") or 0))
    event_ids = [str(event["event_id"]) for event in ordered if event.get("event_id")]
    duplicate_ids = sorted(
        event_id for event_id, count in Counter(event_ids).items() if count > 1
    )
    sequences = [event.get("sequence") for event in ordered]
    numeric_sequences = [value for value in sequences if isinstance(value, int)]
    sequence_ok = (
        len(numeric_sequences) == len(ordered)
        and numeric_sequences == sorted(numeric_sequences)
        and len(set(numeric_sequences)) == len(numeric_sequences)
    )
    run_ids = {str(event.get("run_id")) for event in ordered if event.get("run_id")}
    trace_ids = {
        str(event.get("trace_id")) for event in ordered if event.get("trace_id")
    }
    terminal = next(
        (event for event in reversed(ordered) if event.get("type") in TERMINAL_TYPES),
        None,
    )
    assertions = [
        _assertion("start_event", bool(ordered and ordered[0].get("type") == "start"), "first event is start"),
        _assertion("terminal_event", terminal is not None, "run contains done, error, or cancelled"),
        _assertion("event_ids", len(event_ids) == len(ordered), "every event has an event_id"),
        _assertion("unique_event_ids", not duplicate_ids, "event_id values are unique"),
        _assertion("sequence", sequence_ok, "sequence values are present, ordered, and unique"),
        _assertion("run_id", len(run_ids) == 1, "events share one run_id"),
        _assertion("trace_id", len(trace_ids) == 1, "events share one trace_id"),
    ]

    first_ts = next((_timestamp(event) for event in ordered if _timestamp(event) is not None), None)
    milestones: list[dict[str, Any]] = []
    for index, event in enumerate(ordered):
        timestamp = _timestamp(event)
        next_timestamp = (
            _timestamp(ordered[index + 1]) if index + 1 < len(ordered) else None
        )
        milestones.append(
            {
                "type": event.get("type"),
                "step": event.get("step"),
                "sequence": event.get("sequence"),
                "timestamp": timestamp,
                "offset_ms": timestamp - first_ts if timestamp is not None and first_ts is not None else None,
                "gap_ms": next_timestamp - timestamp if timestamp is not None and next_timestamp is not None else None,
            }
        )

    calls: dict[str, dict[str, Any]] = {}
    tools: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    approval_id: str | None = None
    approval_status: str | None = None
    for event in ordered:
        if event.get("type") == "error":
            data = dict(event.get("data") or {})
            errors.append({"code": data.get("code"), "message": data.get("message")})
        if event.get("type") == "x.bridge.approval_required":
            data = dict(event.get("data") or {})
            approval_id = str(data.get("approval_id") or "") or approval_id
            approval_status = "pending"
        elif event.get("type") == "x.bridge.approval_resolved":
            data = dict(event.get("data") or {})
            approval_id = str(data.get("approval_id") or "") or approval_id
            approval_status = str(data.get("decision") or "resolved")
        if event.get("type") not in {"tool_call", "tool_result"}:
            continue
        data = dict(event.get("data") or {})
        call_id = str(data.get("tool_call_id") or data.get("id") or data.get("name") or "unknown")
        if event.get("type") == "tool_call":
            calls[call_id] = {
                "tool_call_id": call_id,
                "name": data.get("name"),
                "args": data.get("args"),
                "started_at": _timestamp(event),
                "call_sequence": event.get("sequence"),
            }
            continue
        call = calls.pop(call_id, {"tool_call_id": call_id, "name": data.get("name")})
        ended_at = _timestamp(event)
        started_at = call.get("started_at")
        call.update(
            {
                "result": data,
                "ended_at": ended_at,
                "result_sequence": event.get("sequence"),
                "duration_ms": ended_at - started_at if isinstance(ended_at, int) and isinstance(started_at, int) else None,
            }
        )
        tools.append(call)
    tools.extend({**call, "result": None, "duration_ms": None} for call in calls.values())

    last_ts = next((_timestamp(event) for event in reversed(ordered) if _timestamp(event) is not None), None)
    return {
        "run_id": next(iter(run_ids), None),
        "trace_id": next(iter(trace_ids), None),
        "terminal": terminal.get("type") if terminal else None,
        "event_count": len(ordered),
        "duration_ms": last_ts - first_ts if first_ts is not None and last_ts is not None else None,
        "contract_ok": all(item["passed"] for item in assertions),
        "assertions": assertions,
        "duplicate_event_ids": duplicate_ids,
        "milestones": milestones,
        "tools": tools,
        "tool_count": len(tools),
        "errors": errors,
        "error": errors[-1] if errors else None,
        "approval_id": approval_id,
        "approval_status": approval_status,
        "event_types": dict(Counter(str(event.get("type")) for event in ordered)),
    }
