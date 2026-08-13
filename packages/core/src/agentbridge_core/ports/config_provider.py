"""ConfigProvider protocol — hot-reconfigurable tier-A settings."""

from __future__ import annotations

from typing import Any, Protocol


class ConfigProvider(Protocol):
    async def get(self, key: str) -> Any | None: ...

    async def set(
        self, key: str, value: Any, *, updated_by: str | None = None
    ) -> None: ...
