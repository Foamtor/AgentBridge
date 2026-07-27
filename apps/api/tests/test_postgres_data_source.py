"""PostgresDataSource integration tests (skipped without DSN)."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("AGENTBRIDGE_TEST_PG_DSN"),
    reason="AGENTBRIDGE_TEST_PG_DSN not set",
)


@pytest.mark.asyncio
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
