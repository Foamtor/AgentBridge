"""API test fixtures — fake runtime via env; domains registered in lifespan."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Ensure Settings picks up fake runtime before create_app/lifespan.
os.environ.setdefault("AGENT_BASE_FAKE_RUNTIME", "1")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "1")
    from main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c
