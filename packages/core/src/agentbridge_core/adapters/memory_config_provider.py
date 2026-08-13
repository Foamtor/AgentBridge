"""In-memory ConfigProvider for tests and dev."""

from __future__ import annotations

from typing import Any


class MemoryConfigProvider:
    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    async def get(self, key: str) -> Any | None:
        return self._values.get(key)

    async def set(
        self, key: str, value: Any, *, updated_by: str | None = None
    ) -> None:
        _ = updated_by
        self._values[key] = value
