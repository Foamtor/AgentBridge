"""API test fixtures — fake runtime via env; domains registered in lifespan."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from testing.app_factory import create_test_app, ensure_api_on_path

ensure_api_on_path()

# Ensure Settings picks up fake runtime before create_app/lifespan.
os.environ.setdefault("AGENT_BASE_FAKE_RUNTIME", "1")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "1")
    app = create_test_app()
    with TestClient(app) as c:
        yield c
