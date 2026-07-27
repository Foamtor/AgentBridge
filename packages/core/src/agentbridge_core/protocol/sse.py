"""SSE serialization helpers."""

from __future__ import annotations

import json
from typing import Any


def format_sse_line(event: dict[str, Any]) -> str:
    """Serialize an event dict as one SSE `data:` frame."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
