"""Port and in-memory adapter for tenant-scoped run annotations."""

from __future__ import annotations

from typing import Any, Protocol


class RunAnnotationStore(Protocol):
    async def create(self, annotation: dict[str, Any]) -> dict[str, Any]: ...

    async def list_for_run(
        self, tenant_id: str, run_id: str
    ) -> list[dict[str, Any]]: ...

    async def list_for_tenant(self, tenant_id: str) -> list[dict[str, Any]]: ...

    async def delete(self, tenant_id: str, annotation_id: str) -> bool: ...


class MemoryRunAnnotationStore:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    async def create(self, annotation: dict[str, Any]) -> dict[str, Any]:
        item = dict(annotation)
        self._items[str(item["annotation_id"])] = item
        return dict(item)

    async def list_for_run(
        self, tenant_id: str, run_id: str
    ) -> list[dict[str, Any]]:
        return [
            dict(item)
            for item in self._items.values()
            if item.get("tenant_id") == tenant_id and item.get("run_id") == run_id
        ]

    async def list_for_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        return [
            dict(item)
            for item in self._items.values()
            if item.get("tenant_id") == tenant_id
        ]

    async def delete(self, tenant_id: str, annotation_id: str) -> bool:
        item = self._items.get(annotation_id)
        if item is None or item.get("tenant_id") != tenant_id:
            return False
        del self._items[annotation_id]
        return True
