"""API test fixtures — fake runtime via env; domains registered in lifespan."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from testing.app_factory import create_test_app, ensure_api_on_path

ensure_api_on_path()

# Ensure Settings picks up fake runtime before create_app/lifespan.
os.environ.setdefault("AGENTBRIDGE_FAKE_RUNTIME", "1")


@pytest.fixture(autouse=True)
def restore_environment_after_test():
    """Undo direct ``os.environ`` writes made by legacy API tests.

    Some tests predate consistent ``monkeypatch`` usage and directly assign
    settings such as auth secrets or runtime backends.  A full snapshot keeps
    those assignments from leaking into later tests when core and API suites
    are collected in one pytest process.
    """

    original = dict(os.environ)
    yield
    for key in set(os.environ) - set(original):
        del os.environ[key]
    os.environ.update(original)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    app = create_test_app()
    with TestClient(app) as c:
        yield c
