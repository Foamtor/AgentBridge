"""No-op DataSource when ENABLE_DATA_SOURCE is false."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from agentbridge_core.ports.data_source import DataSource

T = TypeVar("T")


class NoopDataSource:
    async def query(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        return []

    async def execute(self, sql: str, *params: Any) -> int:
        return 0

    async def transaction(self, operation: Callable[[DataSource], Awaitable[T]]) -> T:
        return await operation(self)

    async def close(self) -> None:
        return None
