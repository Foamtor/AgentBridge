"""Admin token usage API tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


def test_production_usage_store_is_postgres() -> None:
    from adapters.postgres_usage_store import PostgresUsageStore
    from config.settings import Settings
    from lifespan import _build_usage_store

    settings = Settings(
        _env_file=None,
        AGENTBRIDGE_FAKE_RUNTIME=False,
        PG_DSN="postgresql://u:p@db/agentbridge",
    )

    assert isinstance(_build_usage_store(settings), PostgresUsageStore)


def test_usage_tokens_group_by_route(client) -> None:
    r = client.get("/admin/usage/tokens?group_by=route")
    assert r.status_code == 200
    body = r.json()
    assert body["group_by"] == "route"
    assert "items" in body


def test_usage_tokens_empty_returns_200_empty_items(client) -> None:
    r = client.get("/admin/usage/tokens?group_by=model")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_usage_tokens_invalid_group_by(client) -> None:
    r = client.get("/admin/usage/tokens?group_by=invalid")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_group_by"


def test_usage_tokens_respects_time_window(client) -> None:
    store = client.app.state.usage_store
    store.record(
        tenant_id="dev",
        route="echo",
        model="gpt-4o",
        input_tokens=10,
        output_tokens=5,
        recorded_at="2020-01-01T00:00:00+00:00",
    )
    store.record(
        tenant_id="dev",
        route="echo",
        model="gpt-4o",
        input_tokens=20,
        output_tokens=8,
        recorded_at="2030-01-01T00:00:00+00:00",
    )
    r = client.get(
        "/admin/usage/tokens?group_by=route&since=2029-01-01T00:00:00Z"
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["input_tokens"] == 20
    assert body["items"][0]["model"] == "gpt-4o"


def test_usage_tokens_do_not_return_another_tenant(client) -> None:
    store = client.app.state.usage_store
    store.record(
        tenant_id="dev",
        route="echo",
        model="gpt-4o",
        input_tokens=3,
        output_tokens=2,
    )
    store.record(
        tenant_id="other-tenant",
        route="echo",
        model="gpt-4o",
        input_tokens=99,
        output_tokens=99,
    )

    response = client.get("/admin/usage/tokens?group_by=route")

    assert response.status_code == 200
    assert response.json()["totals"] == {"input_tokens": 3, "output_tokens": 2}
    assert response.json()["items"] == [
        {
            "tenant_id": "dev",
            "route": "echo",
            "model": "gpt-4o",
            "input_tokens": 3,
            "output_tokens": 2,
        }
    ]


def test_usage_tokens_can_be_filtered_to_one_run(client) -> None:
    store = client.app.state.usage_store
    store.record(
        tenant_id="dev",
        route="echo",
        model="gpt-4o",
        input_tokens=3,
        output_tokens=2,
        run_id="r-one",
    )
    store.record(
        tenant_id="dev",
        route="echo",
        model="gpt-4o",
        input_tokens=9,
        output_tokens=4,
        run_id="r-two",
    )

    response = client.get("/admin/usage/tokens?group_by=route&run_id=r-one")

    assert response.status_code == 200
    assert response.json()["totals"] == {"input_tokens": 3, "output_tokens": 2}


@pytest.mark.asyncio
async def test_postgres_usage_store_aggregate_binds_tenant_id_first() -> None:
    from adapters.postgres_usage_store import PostgresUsageStore

    captured: dict[str, object] = {}

    class FakeConnection:
        async def fetch(self, sql: str, *args: object):
            captured["sql"] = sql
            captured["args"] = args
            return []

    class Acquire:
        async def __aenter__(self):
            return FakeConnection()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        def acquire(self):
            return Acquire()

    store = PostgresUsageStore("postgresql://unused")
    store._pool = FakePool()  # type: ignore[assignment]
    await store.aggregate(
        group_by="route",
        tenant_id="tenant-a",
        since="2026-01-01T00:00:00Z",
        until="2026-01-02T00:00:00Z",
        run_id="run-1",
    )

    assert captured["args"] == (
        "tenant-a",
        datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc),
        "run-1",
    )
