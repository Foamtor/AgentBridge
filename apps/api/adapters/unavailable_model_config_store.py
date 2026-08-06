"""Explicit no-op store when credential encryption has not been configured."""

from __future__ import annotations

from typing import Any


class UnavailableModelConfigStore:
    async def setup(self) -> None:
        return None

    async def list(self) -> list[dict[str, Any]]:
        return []

    async def get(self, alias: str) -> dict[str, Any] | None:
        return None

    async def create(self, record: dict[str, Any]) -> dict[str, Any] | None:
        return None

    async def update(self, alias: str, record: dict[str, Any]) -> dict[str, Any] | None:
        return None

    async def delete(self, alias: str) -> bool:
        return False

    async def close(self) -> None:
        return None
