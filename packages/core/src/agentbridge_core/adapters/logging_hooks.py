"""Logging RunHooks example — swap in lifespan instead of NoopHooks."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("agentbridge.hooks")


class LoggingHooks:
    async def on_run_end(self, payload: dict[str, Any]) -> None:
        logger.info(
            "run_end thread_id=%s run_id=%s route=%s",
            payload.get("thread_id"),
            payload.get("run_id"),
            payload.get("route"),
        )
