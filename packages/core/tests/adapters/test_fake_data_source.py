"""FakeDataSource seed + filter tests."""

from __future__ import annotations

import pytest
from agent_base_core.adapters.fake_data_source import FakeDataSource
from agent_base_core.adapters.noop_data_source import NoopDataSource


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
async def test_noop_data_source_returns_empty() -> None:
    ds = NoopDataSource()
    assert await ds.query("SELECT 1") == []
    assert await ds.execute("UPDATE x") == 0
