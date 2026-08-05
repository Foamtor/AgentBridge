"""PostgreSQL integration coverage for Plugin Playground evidence stores."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest


async def _apply_observability_migration(dsn: str) -> None:
    import asyncpg

    migration = Path(__file__).resolve().parents[1] / "migrations" / "010_observability.sql"
    connection = await asyncpg.connect(dsn)
    try:
        await connection.execute(migration.read_text(encoding="utf-8"))
    finally:
        await connection.close()


def test_postgres_observability_stores_can_be_constructed() -> None:
    from adapters.postgres_observability_store import (
        PostgresEventLog,
        PostgresMessageStore,
        PostgresRunAnnotationStore,
        PostgresRunStore,
    )

    dsn = "postgresql://unused"
    assert PostgresRunStore(dsn) is not None
    assert PostgresEventLog(dsn) is not None
    assert PostgresMessageStore(dsn) is not None
    assert PostgresRunAnnotationStore(dsn) is not None


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("AGENTBRIDGE_TEST_PG_DSN"),
    reason="AGENTBRIDGE_TEST_PG_DSN not set",
)
async def test_postgres_observability_evidence_survives_new_store_instances() -> None:
    from adapters.postgres_observability_store import (
        PostgresEventLog,
        PostgresMessageStore,
        PostgresRunAnnotationStore,
        PostgresRunStore,
    )

    dsn = os.environ["AGENTBRIDGE_TEST_PG_DSN"]
    await _apply_observability_migration(dsn)
    tenant_id = f"observability-{uuid.uuid4().hex}"
    other_tenant_id = f"other-{uuid.uuid4().hex}"
    run_id = f"r-{uuid.uuid4().hex}"
    thread_id = f"t-{uuid.uuid4().hex}"
    annotation_id = f"ann-{uuid.uuid4().hex}"
    first = (
        PostgresRunStore(dsn),
        PostgresEventLog(dsn),
        PostgresMessageStore(dsn),
        PostgresRunAnnotationStore(dsn),
    )
    try:
        run_store, event_log, message_store, annotation_store = first
        await run_store.upsert(
            {
                "run_id": run_id,
                "tenant_id": tenant_id,
                "thread_id": thread_id,
                "route": "echo",
                "trace_id": run_id,
                "status": "done",
                "started_at": "2026-08-05T00:00:00+00:00",
                "request": {"query": "durable evidence", "extra": {"real": True}},
            }
        )
        for sequence, event_type in ((1, "start"), (2, "done")):
            await event_log.append(
                run_id,
                {
                    "event_id": f"{run_id}-{sequence}",
                    "run_id": run_id,
                    "sequence": sequence,
                    "trace_id": run_id,
                    "type": event_type,
                    "data": {},
                },
                tenant_id=tenant_id,
            )
        await message_store.append_message(
            tenant_id,
            thread_id,
            {"run_id": run_id, "role": "user", "content": "durable evidence"},
        )
        await annotation_store.create(
            {
                "annotation_id": annotation_id,
                "tenant_id": tenant_id,
                "run_id": run_id,
                "author_id": "tester",
                "category": "badcase",
                "rating": "negative",
                "reason": "persist this",
                "expected_behavior": "survive restart",
                "tags": ["persistence"],
                "created_at": "2026-08-05T00:00:00+00:00",
            }
        )
    finally:
        for store in first:
            await store.close()

    second = (
        PostgresRunStore(dsn),
        PostgresEventLog(dsn),
        PostgresMessageStore(dsn),
        PostgresRunAnnotationStore(dsn),
    )
    try:
        run_store, event_log, message_store, annotation_store = second
        stored = await run_store.get(run_id, tenant_id=tenant_id)
        assert stored is not None
        assert stored["request"] == {
            "query": "durable evidence",
            "extra": {"real": True},
        }
        assert [event["type"] for event in await event_log.list(run_id, tenant_id=tenant_id)] == [
            "start",
            "done",
        ]
        assert await message_store.list_messages(tenant_id, thread_id) == [
            {"run_id": run_id, "role": "user", "content": "durable evidence"}
        ]
        assert [item["annotation_id"] for item in await annotation_store.list_for_run(tenant_id, run_id)] == [annotation_id]

        assert await run_store.get(run_id, tenant_id=other_tenant_id) is None
        assert await event_log.list(run_id, tenant_id=other_tenant_id) == []
        assert await message_store.list_messages(other_tenant_id, thread_id) == []
        assert await annotation_store.list_for_run(other_tenant_id, run_id) == []
    finally:
        for store in second:
            await store.close()
