"""PostgreSQL ApprovalStore integration tests."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest


async def _apply_approval_migration(dsn: str) -> None:
    import asyncpg

    migrations = [
        Path(__file__).resolve().parents[1]
        / "migrations"
        / filename
        for filename in ("004_approval_execution.sql", "006_approval_hardening.sql")
    ]
    connection: Any = await asyncpg.connect(dsn)
    try:
        for migration in migrations:
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
        "approval_id": f"test-{uuid.uuid4().hex}",
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
    old = await first.claim_execution(
        approval_id, tenant_id="acme", now=t0, lease_seconds=1
    )
    assert old and old["execution_token"]
    await first.close()

    second = PostgresApprovalStore(dsn)
    try:
        recovered = await second.recover_expired_execution(
            approval_id, tenant_id="acme", now=t0 + timedelta(seconds=2)
        )
        assert recovered and recovered["status"] == "retryable_failed"
        new = await second.claim_execution(
            approval_id,
            tenant_id="acme",
            now=t0 + timedelta(seconds=2),
            lease_seconds=1,
        )
        assert new and new["execution_token"] != old["execution_token"]
        assert (
            await second.mark_succeeded(
                approval_id,
                tenant_id="acme",
                execution_token=old["execution_token"],
                result={"worker": "old"},
            )
            is None
        )
        succeeded = await second.mark_succeeded(
            approval_id,
            tenant_id="acme",
            execution_token=new["execution_token"],
            result={"worker": "new"},
        )
        assert succeeded and succeeded["result"] == {"worker": "new"}
    finally:
        await second.close()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("AGENTBRIDGE_TEST_PG_DSN"),
    reason="AGENTBRIDGE_TEST_PG_DSN not set",
)
async def test_postgres_sequence_is_atomic_across_instances() -> None:
    from adapters.postgres_approval_store import PostgresApprovalStore

    dsn = os.environ["AGENTBRIDGE_TEST_PG_DSN"]
    await _apply_approval_migration(dsn)
    approval_id = f"test-{uuid.uuid4().hex}"
    first = PostgresApprovalStore(dsn)
    second = PostgresApprovalStore(dsn)
    try:
        await first.create(
            {
                "approval_id": approval_id,
                "tenant_id": "acme",
                "sequence": 7,
                "last_sequence": 7,
            }
        )
        values = await asyncio.gather(
            first.next_sequence(approval_id, tenant_id="acme"),
            second.next_sequence(approval_id, tenant_id="acme"),
            first.next_sequence(approval_id, tenant_id="acme"),
            second.next_sequence(approval_id, tenant_id="acme"),
        )
        assert sorted(values) == [8, 9, 10, 11]
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("AGENTBRIDGE_TEST_PG_DSN"),
    reason="AGENTBRIDGE_TEST_PG_DSN not set",
)
async def test_postgres_lists_expired_pending_records_in_stable_order() -> None:
    from adapters.postgres_approval_store import PostgresApprovalStore

    dsn = os.environ["AGENTBRIDGE_TEST_PG_DSN"]
    await _apply_approval_migration(dsn)
    now = datetime(2026, 7, 30, tzinfo=UTC)
    store = PostgresApprovalStore(dsn)
    first_id = f"test-{uuid.uuid4().hex}"
    second_id = f"test-{uuid.uuid4().hex}"
    try:
        for approval_id, tenant_id, expires_at in (
            (second_id, "other", now - timedelta(seconds=1)),
            (first_id, "acme", now - timedelta(seconds=2)),
            (f"test-{uuid.uuid4().hex}", "acme", now + timedelta(seconds=1)),
        ):
            await store.create(
                {
                    "approval_id": approval_id,
                    "tenant_id": tenant_id,
                    "status": "pending",
                    "approval_expires_at": expires_at,
                }
            )
        rows = await store.list_expired_pending(now=now, limit=2)
        assert [row["approval_id"] for row in rows] == [first_id, second_id]
        assert [row["tenant_id"] for row in rows] == ["acme", "other"]
    finally:
        await store.close()
