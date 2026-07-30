"""DataSource protocol — business DB access for tools."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class DataSource(Protocol):
    async def query(self, sql: str, *params: Any) -> list[dict[str, Any]]: ...

    async def execute(self, sql: str, *params: Any) -> int: ...

    async def close(self) -> None: ...


class TransactionalDataSource(DataSource, Protocol):
    async def transaction(self, operation: Callable[[DataSource], Awaitable[T]]) -> T: ...
