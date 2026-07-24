"""Outbound SafetyHooks — last-line redact/warn on emit_text paths."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("agent_base.safety")

_PHONE_RE = re.compile(r"(?<!\d)(1\d{10})(?!\d)")


class SafetyHooks:
    """Scan text_delta content; optionally redact before callers emit."""

    def __init__(self, *, redact: bool = True) -> None:
        self.redact = redact
        self.alerts: list[str] = []

    def on_emit_text(self, text: str, *, ctx_metadata: dict[str, Any] | None = None) -> str:
        _ = ctx_metadata
        if not _PHONE_RE.search(text):
            return text
        msg = "possible phone number in outbound text"
        self.alerts.append(msg)
        logger.warning("safety_hooks: %s", msg)
        if not self.redact:
            return text
        return _PHONE_RE.sub("[REDACTED]", text)
