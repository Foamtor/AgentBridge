"""InputBuilderRegistry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_base_core.errors import UnknownRoute


class InputBuilderRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Callable[..., Any]] = {}

    def register(self, key: str, value: Callable[..., Any]) -> None:
        self._items[key] = value

    def get(self, key: str) -> Callable[..., Any]:
        try:
            return self._items[key]
        except KeyError as exc:
            raise UnknownRoute(key) from exc
