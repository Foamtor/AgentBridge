"""RunStore protocol — run status projection."""

from __future__ import annotations

from typing import Any, Protocol


class RunStore(Protocol):
    async def upsert(self, run: dict[str, Any]) -> None: ...

    async def get(
        self, run_id: str, *, tenant_id: str
    ) -> dict[str, Any] | None: ...

    async def list_by_tenant(self, tenant_id: str) -> list[dict[str, Any]]: ...
