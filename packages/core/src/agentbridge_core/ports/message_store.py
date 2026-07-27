"""MessageStore protocol — conversation projection by tenant + thread."""

from __future__ import annotations

from typing import Any, Protocol


class MessageStore(Protocol):
    async def append_message(
        self, tenant_id: str, thread_id: str, message: dict[str, Any]
    ) -> None: ...

    async def list_messages(
        self, tenant_id: str, thread_id: str
    ) -> list[dict[str, Any]]: ...
