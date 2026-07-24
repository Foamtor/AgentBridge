"""DataFilter protocol — deny-by-default field rules."""

from __future__ import annotations

from typing import Any, Protocol

from agent_base_core.protocol.context import RunContext


class DataFilter(Protocol):
    def apply(self, rows: list[dict[str, Any]], ctx: RunContext) -> list[dict[str, Any]]: ...
