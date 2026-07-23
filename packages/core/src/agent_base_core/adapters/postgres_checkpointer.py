"""PostgresCheckpointerFactory (optional postgres extra)."""

from __future__ import annotations

from typing import Any


class PostgresCheckpointerFactory:
    def __init__(self, conn_string: str) -> None:
        self._conn_string = conn_string
        self._cm: Any = None
        self._checkpointer: Any = None

    async def setup(self) -> None:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        self._cm = AsyncPostgresSaver.from_conn_string(self._conn_string)
        self._checkpointer = await self._cm.__aenter__()
        await self._checkpointer.setup()

    async def get(self) -> Any:
        if self._checkpointer is None:
            await self.setup()
        return self._checkpointer

    async def teardown(self) -> None:
        if self._cm is not None:
            await self._cm.__aexit__(None, None, None)
        self._cm = None
        self._checkpointer = None
