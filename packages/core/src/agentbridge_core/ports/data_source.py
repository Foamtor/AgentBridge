"""DataSource protocol — business DB access for tools."""

from __future__ import annotations

from typing import Any, Protocol


class DataSource(Protocol):
    async def query(self, sql: str, *params: Any) -> list[dict[str, Any]]: ...

    async def execute(self, sql: str, *params: Any) -> int: ...

    async def close(self) -> None: ...
