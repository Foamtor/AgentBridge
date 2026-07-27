"""No-op DataSource when ENABLE_DATA_SOURCE is false."""

from __future__ import annotations

from typing import Any


class NoopDataSource:
    async def query(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        return []

    async def execute(self, sql: str, *params: Any) -> int:
        return 0

    async def close(self) -> None:
        return None
