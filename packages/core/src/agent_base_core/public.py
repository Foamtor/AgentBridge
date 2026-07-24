"""Stable facade for hosts: orchestration_stream / cancel_run.

Must only forward — never construct adapters here.
"""

from __future__ import annotations

from typing import Any


async def orchestration_stream(target: Any, **kwargs: Any) -> None:
    handle = getattr(target, "handle", None)
    if callable(handle):
        await handle(**kwargs)
        return
    await target.start_stream(**kwargs)


async def cancel_run(lifecycle: Any, **kwargs: Any) -> None:
    await lifecycle.cancel(**kwargs)
