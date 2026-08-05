"""Run diagnostics, JSONL export, and generic annotation APIs."""

from __future__ import annotations

import json


def _run(client, *, thread_id: str = "t-diagnostics") -> str:
    response = client.post(
        "/chat/stream",
        json={"query": "hello diagnostics", "thread_id": thread_id, "route": "echo"},
    )
    assert response.status_code == 200
    first = next(
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    )
    return str(first["run_id"])


def test_run_diagnostics_and_jsonl_export(client) -> None:
    run_id = _run(client)

    response = client.get(f"/runs/{run_id}/diagnostics")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["terminal"] == "done"
    assert body["contract_ok"] is True
    assert body["event_count"] >= 2
    assert body["milestones"][0]["type"] == "start"

    exported = client.get(f"/runs/{run_id}/events.jsonl")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/x-ndjson")
    lines = [json.loads(line) for line in exported.text.splitlines()]
    assert lines[0]["type"] == "start"
    assert lines[-1]["type"] == "done"


def test_run_annotations_are_generic_and_deletable(client) -> None:
    run_id = _run(client, thread_id="t-annotation")
    created = client.post(
        f"/runs/{run_id}/annotations",
        json={
            "category": "badcase",
            "rating": "negative",
            "reason": "Expected a more specific answer",
            "expected_behavior": "Mention the selected route",
            "tags": ["quality", "quality", " regression "],
        },
    )
    assert created.status_code == 201
    annotation = created.json()
    assert annotation["run_id"] == run_id
    assert annotation["tags"] == ["quality", "regression"]
    assert client.app.state.audit.records[-1]["action"] == "console.run_annotation_create"

    listed = client.get(f"/runs/{run_id}/annotations")
    assert listed.status_code == 200
    assert [item["annotation_id"] for item in listed.json()] == [
        annotation["annotation_id"]
    ]

    deleted = client.delete(
        f"/runs/{run_id}/annotations/{annotation['annotation_id']}"
    )
    assert deleted.status_code == 204
    assert client.app.state.audit.records[-1]["action"] == "console.run_annotation_delete"
    assert client.get(f"/runs/{run_id}/annotations").json() == []


def test_aggregate_diagnostics_counts_runs_and_badcases(client) -> None:
    run_id = _run(client, thread_id="t-diagnostic-summary")
    client.post(
        f"/runs/{run_id}/annotations",
        json={"category": "badcase", "rating": "negative", "reason": "incorrect"},
    )

    response = client.get("/admin/diagnostics")
    assert response.status_code == 200
    body = response.json()
    assert body["total_runs"] >= 1
    assert body["badcases"] == 1
    assert body["by_route"]["echo"]["runs"] >= 1


def test_run_request_snapshot_supports_replay(client) -> None:
    response = client.post(
        "/chat/stream",
        json={
            "query": "remember this",
            "thread_id": "t-replay-request",
            "route": "echo",
            "model": "default",
            "extra": {"debug": True},
        },
    )
    run_id = next(
        json.loads(line[6:])["run_id"]
        for line in response.text.splitlines()
        if line.startswith("data: ")
    )
    run = client.get(f"/runs/{run_id}").json()
    assert run["request"] == {
        "query": "remember this",
        "thread_id": "t-replay-request",
        "route": "echo",
        "model": "default",
        "extra": {"debug": True},
    }
    assert run["trace_id"] == run_id
