"""API test fixtures — fake runtime via env; domains registered in lifespan."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from testing.app_factory import create_test_app, ensure_api_on_path

ensure_api_on_path()

# Keep API tests independent from the developer's root .env.  Individual
# tests override these values when they intentionally exercise another mode.
os.environ.update(
    {
        "AGENTBRIDGE_FAKE_RUNTIME": "1",
        "AUTH_MODE": "",
        "AUTH_REQUIRED": "false",
        "AUTH_DEV_STUB": "false",
        "ENABLE_DATA_SOURCE": "false",
        "KNOWLEDGE_BACKEND": "fake",
        "OBSERVABILITY_STORE_BACKEND": "memory",
        "RUNTIME_CONFIG_BACKEND": "memory",
        "USE_MEMORY_CHECKPOINTER": "true",
    }
)


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
