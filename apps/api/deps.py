"""FastAPI dependencies (get_run_lifecycle)."""

from __future__ import annotations

from fastapi import Request

from agent_base_core.application.run_lifecycle import RunLifecycle


def get_run_lifecycle(request: Request) -> RunLifecycle:
    return request.app.state.run_lifecycle
