"""ToolRegistry."""

from __future__ import annotations

from typing import Any

from agent_base_core.errors import UnknownRoute


class ToolRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Any] = {}

    def register(self, key: str, value: Any) -> None:
        self._items[key] = value

    def get(self, key: str) -> Any:
        try:
            return self._items[key]
        except KeyError as exc:
            raise UnknownRoute(key) from exc

    def keys(self) -> list[str]:
        return sorted(self._items.keys())
