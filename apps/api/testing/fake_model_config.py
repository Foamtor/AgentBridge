"""Test-only substitute for the PostgreSQL model configuration store."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class FakeModelConfigStore:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    async def setup(self) -> None:
        return None

    async def list(self) -> list[dict[str, Any]]:
        return [dict(self.records[key]) for key in sorted(self.records)]

    async def get(self, alias: str) -> dict[str, Any] | None:
        row = self.records.get(alias)
        return dict(row) if row is not None else None

    async def create(self, record: dict[str, Any]) -> dict[str, Any] | None:
        if record["alias"] in self.records:
            return None
        self.records[record["alias"]] = dict(record)
        return dict(record)

    async def update(self, alias: str, record: dict[str, Any]) -> dict[str, Any] | None:
        if alias not in self.records:
            return None
        self.records[alias] = {**self.records[alias], **record, "alias": alias}
        return dict(self.records[alias])

    async def delete(self, alias: str) -> bool:
        return self.records.pop(alias, None) is not None

    async def record_test(
        self,
        alias: str,
        *,
        status: str,
        latency_ms: int | None,
        error: str | None,
        capability: str | None,
    ) -> dict[str, Any] | None:
        record = self.records.get(alias)
        if record is None:
            return None
        record.update({
            "last_test_status": status,
            "last_tested_at": datetime.now(timezone.utc).isoformat(),
            "last_test_latency_ms": latency_ms,
            "last_test_error": error,
            "last_test_capability": capability,
        })
        return dict(record)

    async def close(self) -> None:
        return None
