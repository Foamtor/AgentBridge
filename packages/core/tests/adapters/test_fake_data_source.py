"""FakeDataSource seed + filter tests."""

from __future__ import annotations

import pytest
from agentbridge_core.adapters.fake_data_source import FakeDataSource
from agentbridge_core.adapters.noop_data_source import NoopDataSource


@pytest.mark.asyncio
async def test_fake_data_source_filters_by_params() -> None:
    ds = FakeDataSource()
    ds.seed(
        "demo_orders",
        [
            {"id": 1, "tenant_id": "acme", "status": "open"},
            {"id": 2, "tenant_id": "acme", "status": "closed"},
            {"id": 3, "tenant_id": "other", "status": "open"},
        ],
    )
    rows = await ds.query(
        "SELECT id, status FROM demo_orders WHERE status = $1 AND tenant_id = $2",
        "open",
        "acme",
    )
    assert rows == [{"id": 1, "tenant_id": "acme", "status": "open"}]
    assert ds.last_params == ("open", "acme")


@pytest.mark.asyncio
async def test_fake_transaction_rolls_back_on_error() -> None:
    ds = FakeDataSource()
    ds.seed("items", [{"id": "before", "tenant_id": "acme"}])

    async def operation(tx) -> None:
        await tx.execute(
            "INSERT INTO items (id, tenant_id) VALUES ($1, $2)",
            "after",
            "acme",
        )
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await ds.transaction(operation)

    assert await ds.query("SELECT * FROM items WHERE tenant_id = $1", "acme") == [
        {"id": "before", "tenant_id": "acme"}
    ]


@pytest.mark.asyncio
async def test_fake_insert_respects_postgres_placeholder_positions() -> None:
    ds = FakeDataSource()

    await ds.execute(
        "INSERT INTO items (id, tenant_id) VALUES ($2, $1)",
        "tenant-a",
        "item-a",
    )

    rows = await ds.query(
        "SELECT * FROM items WHERE tenant_id = $1", "tenant-a"
    )

    assert rows == [{"id": "item-a", "tenant_id": "tenant-a"}]


@pytest.mark.asyncio
async def test_fake_query_respects_postgres_placeholder_positions() -> None:
    ds = FakeDataSource()
    ds.seed(
        "items",
        [
            {"id": "item-a", "tenant_id": "tenant-a", "status": "open"},
            {"id": "item-b", "tenant_id": "tenant-a", "status": "closed"},
        ],
    )

    rows = await ds.query(
        "SELECT * FROM items WHERE tenant_id = $2 AND status = $1",
        "open",
        "tenant-a",
    )

    assert rows == [{"id": "item-a", "tenant_id": "tenant-a", "status": "open"}]


@pytest.mark.asyncio
async def test_fake_query_rejects_invalid_postgres_placeholder() -> None:
    ds = FakeDataSource()

    with pytest.raises(ValueError, match=r"start at \$1"):
        await ds.query("SELECT * FROM items WHERE tenant_id = $0", "tenant-a")


@pytest.mark.asyncio
async def test_noop_data_source_returns_empty() -> None:
    ds = NoopDataSource()
    assert await ds.query("SELECT 1") == []
    assert await ds.execute("UPDATE x") == 0
