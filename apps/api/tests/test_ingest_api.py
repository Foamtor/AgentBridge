"""POST /ingest API tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from jose import jwt


def test_ingest_fake_backend_and_searchable(client) -> None:
    r = client.post(
        "/ingest",
        json={
            "docs": [
                {
                    "chunk_id": "rb-1",
                    "text": "AgentBridge ingest pipeline works",
                    "doc_id": "doc-rb",
                }
            ]
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["ingested_count"] == 1
    assert body["job_id"].startswith("ing-")

    status = client.get("/admin/knowledge/status")
    assert status.status_code == 200
    jobs = status.json()["ingest_jobs"]
    assert len(jobs) >= 1
    assert jobs[0]["status"] == "completed"

    search = client.post(
        "/admin/knowledge/search",
        json={"query": "AgentBridge pipeline"},
    )
    assert search.status_code == 200
    assert search.json()["hits"] == [
        {
            "chunk_id": "rb-1",
            "doc_id": "doc-rb",
            "text": "AgentBridge ingest pipeline works",
            "score": 2.0,
            "metadata": {},
        }
    ]


def test_ingest_rejects_empty_docs(client) -> None:
    r = client.post("/ingest", json={"docs": []})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_request"


def test_ingest_rejects_invalid_doc(client) -> None:
    r = client.post("/ingest", json={"docs": [{"text": "no id"}]})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_doc"


def test_ingest_unsupported_for_external_backend(client) -> None:
    from agentbridge_core.adapters.unsupported_knowledge_ingest import (
        UnsupportedKnowledgeIngest,
    )

    client.app.state.knowledge_ingest = UnsupportedKnowledgeIngest("external")
    r = client.post(
        "/ingest",
        json={"docs": [{"chunk_id": "x", "text": "y"}]},
    )
    assert r.status_code == 501
    assert r.json()["detail"]["code"] == "unsupported"


def test_ingest_requires_knowledge_write(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "ingest-perm-secret"
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_DEV_STUB", "false")
    monkeypatch.setenv("OIDC_JWT_SECRET", secret)
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["AUTH_DEV_STUB"] = "false"
    os.environ["OIDC_JWT_SECRET"] = secret
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    token = jwt.encode(
        {
            "sub": "u-viewer",
            "tenant_id": "default",
            "roles": ["viewer"],
            "permissions": ["admin:read"],
        },
        secret,
        algorithm="HS256",
    )
    with TestClient(app) as c:
        r = c.post(
            "/ingest",
            headers={"Authorization": f"Bearer {token}"},
            json={"docs": [{"chunk_id": "x", "text": "y"}]},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "forbidden"
