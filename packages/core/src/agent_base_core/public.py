"""Stable facade for hosts: orchestration_stream / cancel_run.

Must only forward to an injected RunLifecycle — never construct adapters here.
"""

from __future__ import annotations

from typing import Any

from agent_base_core.application.run_lifecycle import RunLifecycle


async def orchestration_stream(lifecycle: RunLifecycle, **kwargs: Any) -> None:
    await lifecycle.start_stream(**kwargs)


async def cancel_run(lifecycle: RunLifecycle, **kwargs: Any) -> None:
    await lifecycle.cancel(**kwargs)
