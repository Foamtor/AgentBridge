"""In-memory token usage aggregation store."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class MemoryUsageStore:
    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def record(
        self,
        *,
        tenant_id: str,
        route: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        run_id: str | None = None,
        event_id: str | None = None,
        recorded_at: str | None = None,
    ) -> None:
        self._records.append(
            {
                "tenant_id": tenant_id,
                "route": route,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "run_id": run_id,
                "event_id": event_id,
                "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
            }
        )

    def _in_window(
        self, rec: dict[str, Any], since: str | None, until: str | None
    ) -> bool:
        since_dt = _parse_iso(since)
        until_dt = _parse_iso(until)
        recorded = _parse_iso(str(rec.get("recorded_at") or ""))
        if since_dt and (recorded is None or recorded < since_dt):
            return False
        return not (until_dt and (recorded is None or recorded > until_dt))

    def aggregate(
        self,
        *,
        group_by: str,
        since: str | None = None,
        until: str | None = None,
        tenant_id: str,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        buckets: dict[tuple[Any, ...], dict[str, Any]] = {}
        total_in = 0
        total_out = 0
        for rec in self._records:
            if rec["tenant_id"] != tenant_id:
                continue
            if run_id is not None and rec.get("run_id") != run_id:
                continue
            if not self._in_window(rec, since, until):
                continue
            if group_by == "tenant":
                key = (rec["tenant_id"],)
            elif group_by == "route":
                key = (rec["tenant_id"], rec["route"], rec["model"])
            else:
                key = (rec["tenant_id"], rec["route"], rec["model"])
            if key not in buckets:
                buckets[key] = {
                    "tenant_id": rec["tenant_id"],
                    "route": rec["route"],
                    "model": rec["model"],
                    "run_id": rec.get("run_id"),
                    "event_id": rec.get("event_id"),
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
            buckets[key]["input_tokens"] += int(rec["input_tokens"])
            buckets[key]["output_tokens"] += int(rec["output_tokens"])
            total_in += int(rec["input_tokens"])
            total_out += int(rec["output_tokens"])
        items = list(buckets.values())
        if run_id is None:
            for item in items:
                item.pop("run_id", None)
                item.pop("event_id", None)
        if group_by == "tenant":
            items = [
                {
                    "tenant_id": i["tenant_id"],
                    "input_tokens": i["input_tokens"],
                    "output_tokens": i["output_tokens"],
                }
                for i in items
            ]
        elif group_by == "model":
            merged: dict[str, dict[str, Any]] = {}
            for i in items:
                model = str(i["model"])
                if model not in merged:
                    merged[model] = {
                        "model": model,
                        "input_tokens": 0,
                        "output_tokens": 0,
                    }
                merged[model]["input_tokens"] += i["input_tokens"]
                merged[model]["output_tokens"] += i["output_tokens"]
            items = list(merged.values())
        return {
            "window": {"since": since, "until": until},
            "group_by": group_by,
            "items": items,
            "totals": {"input_tokens": total_in, "output_tokens": total_out},
        }
