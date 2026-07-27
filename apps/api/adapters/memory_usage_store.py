"""In-memory token usage aggregation store."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


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
        recorded_at: str | None = None,
    ) -> None:
        self._records.append(
            {
                "tenant_id": tenant_id,
                "route": route,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
            }
        )

    def aggregate(
        self,
        *,
        group_by: str,
        since: str | None = None,
        until: str | None = None,
    ) -> dict[str, Any]:
        key_map = {
            "tenant": "tenant_id",
            "route": "route",
            "model": "model",
        }
        field = key_map[group_by]
        buckets: dict[tuple[Any, ...], dict[str, Any]] = {}
        total_in = 0
        total_out = 0
        for rec in self._records:
            bucket_key = (rec["tenant_id"], rec["route"], rec["model"])
            if field == "tenant_id":
                group_val = rec["tenant_id"]
            elif field == "route":
                group_val = rec["route"]
            else:
                group_val = rec["model"]
            key = (group_val, rec["tenant_id"], rec["route"], rec["model"])
            if key not in buckets:
                buckets[key] = {
                    "tenant_id": rec["tenant_id"],
                    "route": rec["route"],
                    "model": rec["model"],
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
            buckets[key]["input_tokens"] += int(rec["input_tokens"])
            buckets[key]["output_tokens"] += int(rec["output_tokens"])
            total_in += int(rec["input_tokens"])
            total_out += int(rec["output_tokens"])
        items = list(buckets.values())
        if group_by == "tenant":
            items = [
                {
                    "tenant_id": i["tenant_id"],
                    "input_tokens": i["input_tokens"],
                    "output_tokens": i["output_tokens"],
                }
                for i in items
            ]
        elif group_by == "route":
            items = [
                {
                    "tenant_id": i["tenant_id"],
                    "route": i["route"],
                    "input_tokens": i["input_tokens"],
                    "output_tokens": i["output_tokens"],
                }
                for i in items
            ]
        return {
            "window": {"since": since, "until": until},
            "group_by": group_by,
            "items": items,
            "totals": {"input_tokens": total_in, "output_tokens": total_out},
        }
