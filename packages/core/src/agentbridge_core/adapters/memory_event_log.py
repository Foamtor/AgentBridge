"""In-memory EventLog: full committed envelopes including text_delta."""

from __future__ import annotations

from typing import Any


class MemoryEventLog:
    def __init__(self) -> None:
        self._by_run: dict[str, list[dict[str, Any]]] = {}
        self._tenant_of: dict[str, str] = {}

    async def append(
        self, run_id: str, event: dict[str, Any], *, tenant_id: str
    ) -> None:
        owner = self._tenant_of.get(run_id)
        if owner is not None and owner != tenant_id:
            raise PermissionError("cross_tenant")
        self._tenant_of[run_id] = tenant_id
        self._by_run.setdefault(run_id, []).append(event)

    async def list(
        self, run_id: str, *, tenant_id: str
    ) -> list[dict[str, Any]]:
        if self._tenant_of.get(run_id) != tenant_id:
            return []
        return list(self._by_run.get(run_id, []))
