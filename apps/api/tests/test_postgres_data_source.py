"""PostgresDataSource integration tests (skipped without DSN)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest


class _FakeTransaction:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def __aenter__(self) -> None:
        self._events.append("begin")

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> None:
        self._events.append("rollback" if exc is not None else "commit")


class _FakeConnection:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction(self._events)

    async def execute(self, sql: str, *params: Any) -> str:
        self._events.append(f"execute:{sql}:{params}")
        return "UPDATE 1"

    async def fetch(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        self._events.append(f"fetch:{sql}:{params}")
        return [{"id": "item-a"}]


class _FakePool:
    def __init__(self) -> None:
        self.events: list[str] = []
        self._connection = _FakeConnection(self.events)

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[_FakeConnection]:
        self.events.append("acquire")
        try:
            yield self._connection
        finally:
            self.events.append("release")


@pytest.mark.asyncio
async def test_postgres_transaction_reuses_one_connection() -> None:
    from adapters.postgres_data_source import PostgresDataSource

    pool = _FakePool()
    ds = PostgresDataSource("postgresql://unused")
    ds._pool = pool

    async def operation(tx: Any) -> list[dict[str, Any]]:
        assert await tx.execute("UPDATE items SET status = $1", "open") == 1
        return await tx.query("SELECT id FROM items WHERE status = $1", "open")

    assert await ds.transaction(operation) == [{"id": "item-a"}]
    assert pool.events == [
        "acquire",
        "begin",
        "execute:UPDATE items SET status = $1:('open',)",
        "fetch:SELECT id FROM items WHERE status = $1:('open',)",
        "commit",
        "release",
    ]


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("AGENTBRIDGE_TEST_PG_DSN"),
    reason="AGENTBRIDGE_TEST_PG_DSN not set",
)
async def test_postgres_data_source_roundtrip() -> None:
    from adapters.postgres_data_source import PostgresDataSource

    dsn = os.environ["AGENTBRIDGE_TEST_PG_DSN"]
    ds = PostgresDataSource(dsn)
    try:
        await ds.execute(
            """
            CREATE TABLE IF NOT EXISTS demo_orders (
              id int PRIMARY KEY,
              tenant_id text NOT NULL,
              status text NOT NULL
            )
            """
        )
        await ds.execute("DELETE FROM demo_orders WHERE id = $1", 9001)
        await ds.execute(
            "INSERT INTO demo_orders (id, tenant_id, status) VALUES ($1, $2, $3)",
            9001,
            "test-tenant",
            "open",
        )
        rows = await ds.query(
            "SELECT id, status FROM demo_orders WHERE status = $1 AND tenant_id = $2",
            "open",
            "test-tenant",
        )
        assert any(r["id"] == 9001 for r in rows)
    finally:
        await ds.close()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("AGENTBRIDGE_TEST_PG_DSN"),
    reason="AGENTBRIDGE_TEST_PG_DSN not set",
)
async def test_postgres_transaction_rolls_back() -> None:
    from adapters.postgres_data_source import PostgresDataSource

    ds = PostgresDataSource(os.environ["AGENTBRIDGE_TEST_PG_DSN"])
    try:
        await ds.execute(
            """
            CREATE TABLE IF NOT EXISTS demo_orders (
              id int PRIMARY KEY,
              tenant_id text NOT NULL,
              status text NOT NULL
            )
            """
        )
        await ds.execute("DELETE FROM demo_orders WHERE id = $1", 9002)

        async def operation(tx: Any) -> None:
            await tx.execute(
                "INSERT INTO demo_orders (id, tenant_id, status) VALUES ($1, $2, $3)",
                9002,
                "test-tenant",
                "open",
            )
            raise RuntimeError("force rollback")

        with pytest.raises(RuntimeError, match="force rollback"):
            await ds.transaction(operation)

        rows = await ds.query("SELECT id FROM demo_orders WHERE id = $1", 9002)
        assert rows == []
    finally:
        await ds.close()
