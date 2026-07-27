"""In-memory RunStore."""

from __future__ import annotations

from typing import Any


class MemoryRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}

    async def upsert(self, run: dict[str, Any]) -> None:
        run_id = str(run["run_id"])
        existing = self._runs.get(run_id, {})
        merged = dict(existing)
        merged.update(run)
        self._runs[run_id] = merged

    async def get(self, run_id: str, *, tenant_id: str) -> dict[str, Any] | None:
        raw = self._runs.get(run_id)
        if raw is None or raw.get("tenant_id") != tenant_id:
            return None
        return dict(raw)

    async def list_by_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self._runs.values() if r.get("tenant_id") == tenant_id]
