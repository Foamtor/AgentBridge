"""PostgreSQL ApprovalStore integration tests."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest


async def _apply_approval_migration(dsn: str) -> None:
    import asyncpg

    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "004_approval_execution.sql"
    )
    connection: Any = await asyncpg.connect(dsn)
    try:
        await connection.execute(migration.read_text(encoding="utf-8"))
    finally:
        await connection.close()


def test_postgres_approval_store_can_be_constructed() -> None:
    from adapters.postgres_approval_store import PostgresApprovalStore

    assert PostgresApprovalStore("postgresql://unused") is not None


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("AGENTBRIDGE_TEST_PG_DSN"),
    reason="AGENTBRIDGE_TEST_PG_DSN not set",
)
async def test_postgres_store_recovers_expired_execution_after_new_instance() -> None:
    from adapters.postgres_approval_store import PostgresApprovalStore

    dsn = os.environ["AGENTBRIDGE_TEST_PG_DSN"]
    await _apply_approval_migration(dsn)
    t0 = datetime(2026, 7, 30, tzinfo=UTC)
    record = {
        "tenant_id": "acme",
        "route": "example",
        "run_id": "r1",
        "thread_id": "t1",
        "storage_key": "acme::t1",
        "sequence": 1,
        "action": {"type": "example.write_v1", "payload": {"value": 1}},
        "requester_context": {"user_id": "u", "tenant_id": "acme"},
    }
    first = PostgresApprovalStore(dsn)
    approval_id = await first.create(record)
    await first.decide(approval_id, tenant_id="acme", decision="approve")
    await first.claim_execution(approval_id, tenant_id="acme", now=t0, lease_seconds=1)
    await first.close()

    second = PostgresApprovalStore(dsn)
    try:
        recovered = await second.recover_expired_execution(
            approval_id, tenant_id="acme", now=t0 + timedelta(seconds=2)
        )
        assert recovered and recovered["status"] == "retryable_failed"
        assert await second.claim_execution(
            approval_id,
            tenant_id="acme",
            now=t0 + timedelta(seconds=2),
            lease_seconds=1,
        )
    finally:
        await second.close()
