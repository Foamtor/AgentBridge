"""In-memory MessageStore with tenant isolation."""

from __future__ import annotations

from typing import Any


class MemoryMessageStore:
    def __init__(self) -> None:
        self._msgs: dict[tuple[str, str], list[dict[str, Any]]] = {}

    async def append_message(
        self, tenant_id: str, thread_id: str, message: dict[str, Any]
    ) -> None:
        key = (tenant_id, thread_id)
        self._msgs.setdefault(key, []).append(dict(message))

    async def list_messages(
        self, tenant_id: str, thread_id: str
    ) -> list[dict[str, Any]]:
        return [dict(m) for m in self._msgs.get((tenant_id, thread_id), [])]
