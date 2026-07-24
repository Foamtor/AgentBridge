"""In-memory EventLog: full committed envelopes including text_delta."""

from __future__ import annotations

from typing import Any


class MemoryEventLog:
    def __init__(self) -> None:
        self._by_run: dict[str, list[dict[str, Any]]] = {}

    async def append(self, run_id: str, event: dict[str, Any]) -> None:
        self._by_run.setdefault(run_id, []).append(event)

    async def list(self, run_id: str) -> list[dict[str, Any]]:
        return list(self._by_run.get(run_id, []))
