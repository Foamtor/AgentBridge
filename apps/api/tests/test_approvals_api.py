"""POST /approvals/{id} + demo_approval_write e2e."""

from __future__ import annotations

import asyncio
import json

import pytest
from agentbridge_core.application.run_lifecycle import RunLifecycle
from agentbridge_core.errors import ApprovalStateConflict
from config.settings import Settings
from fastapi.testclient import TestClient
from pydantic import ValidationError


def _parse_sse(body: str) -> list[dict]:
    events: list[dict] = []
    for block in body.split("\n\n"):
        line = block.strip()
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[len("data: ") :]))
    return events


def test_demo_approval_write_and_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "0")
    import os

    os.environ["AGENTBRIDGE_FAKE_RUNTIME"] = "0"
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post(
            "/chat/stream",
            json={
                "query": "please write",
                "thread_id": "t-appr-1",
                "route": "demo_approval_write",
            },
        )
        assert r.status_code == 200
        events = _parse_sse(r.text)
        assert any(e["type"] == "x.bridge.approval_required" for e in events)
        assert not any(e["type"] == "done" for e in events)
        req = next(e for e in events if e["type"] == "x.bridge.approval_required")
        approval_id = req["data"]["approval_id"]
        run_id = req["run_id"]

        # Same thread new run must not 409 (lock released).
        r2 = c.post(
            "/chat/stream",
            json={
                "query": "hello",
                "thread_id": "t-appr-1",
                "route": "echo",
            },
        )
        assert r2.status_code == 200

        decided = c.post(
            f"/approvals/{approval_id}",
            json={"decision": "approve"},
        )
        assert decided.status_code == 200
        body = decided.json()
        assert body["ok"] is True
        assert body["approval"]["decision"] == "approve"

        run = c.get(f"/runs/{run_id}")
        assert run.status_code == 200
        assert run.json()["status"] == "done"


def test_chat_injects_token_map(client: TestClient) -> None:
    seen: dict = {}
    orig = client.app.state.pipeline.handle

    async def _capture(**kwargs):
        seen["ctx"] = kwargs.get("ctx")
        return await orig(**kwargs)

    client.app.state.pipeline.handle = _capture  # type: ignore[method-assign]
    r = client.post(
        "/chat/stream",
        json={"query": "hi", "thread_id": "t-tm", "route": "echo"},
    )
    assert r.status_code == 200
    assert isinstance(seen["ctx"].metadata.get("token_map"), dict)


def test_approval_response_exposes_only_safe_allowlisted_fields(
    client: TestClient,
) -> None:
    secret = "postgresql://admin:secret@db/private SELECT password"

    async def _finalize(**kwargs):
        return {
            "approval_id": kwargs["approval_id"],
            "status": "retryable_failed",
            "decision": "approve",
            "reason": None,
            "run_id": "r-safe",
            "thread_id": "t-safe",
            "result": {"ok": False},
            "action": {"type": "example.write_v1", "payload": {"secret": secret}},
            "requester_context": {"token": secret},
            "execution_token": secret,
            "execution_lease_expires_at": secret,
            "error": secret,
            "result_delivery_error": secret,
        }

    client.app.state.run_lifecycle.finalize_approval = _finalize
    response = client.post(
        "/approvals/ap-safe",
        json={"decision": "approve"},
    )

    assert response.status_code == 200
    approval = response.json()["approval"]
    assert set(approval) <= {
        "approval_id",
        "status",
        "decision",
        "reason",
        "run_id",
        "thread_id",
        "result",
    }
    for forbidden in (
        "action",
        "requester_context",
        "execution_token",
        "execution_lease_expires_at",
        "error",
        "result_delivery_error",
    ):
        assert forbidden not in approval
    assert secret not in response.text


def test_executing_approval_conflict_is_stable_409(client: TestClient) -> None:
    async def _conflict(**kwargs):
        raise ApprovalStateConflict("raw internal conflict detail")

    client.app.state.run_lifecycle.finalize_approval = _conflict
    response = client.post(
        "/approvals/ap-executing",
        json={"decision": "deny"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "code": "approval_state_conflict",
            "message": "approval is executing",
        }
    }
    assert "raw internal conflict detail" not in response.text


@pytest.mark.parametrize("interval", [0, -0.01])
def test_approval_expiry_scan_interval_must_be_positive(interval: float) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APPROVAL_EXPIRY_SCAN_INTERVAL_SECONDS=interval,
        )


def test_approval_expiry_scan_interval_defaults_to_thirty_seconds() -> None:
    settings = Settings(_env_file=None)

    assert settings.approval_expiry_scan_interval_seconds == 30.0


@pytest.mark.asyncio
async def test_lifespan_cancels_approval_expiry_scanner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    monkeypatch.setenv("APPROVAL_EXPIRY_SCAN_INTERVAL_SECONDS", "0.01")
    from testing.app_factory import create_test_app

    second_scan = asyncio.Event()
    scan_calls = 0

    async def _scan(self, *, now, limit=100):
        nonlocal scan_calls
        scan_calls += 1
        if scan_calls >= 2:
            second_scan.set()
        return 0

    monkeypatch.setattr(RunLifecycle, "expire_pending_approvals", _scan)
    original_create_task = asyncio.create_task
    scanner_tasks: list[asyncio.Task] = []

    def _capture_task(coro, *args, **kwargs):
        task = original_create_task(coro, *args, **kwargs)
        code = getattr(coro, "cr_code", None)
        if code is not None and code.co_name == "_approval_expiry_loop":
            scanner_tasks.append(task)
        return task

    monkeypatch.setattr(asyncio, "create_task", _capture_task)
    app = create_test_app()

    async with app.router.lifespan_context(app):
        await asyncio.wait_for(second_scan.wait(), timeout=1)
        assert len(scanner_tasks) == 1
        assert not scanner_tasks[0].done()

    assert scan_calls >= 2
    assert scanner_tasks[0].done()
    assert scanner_tasks[0].cancelled()
