"""Platform-first PromptRegistry with optional file fallback."""

from __future__ import annotations

from typing import Any


class LayeredPromptRegistry:
    """Resolve prompts: published platform entry wins, else file fallback."""

    def __init__(self, platform: Any, fallback: Any | None = None) -> None:
        self._platform = platform
        self._fallback = fallback

    def _published_content(self, name: str) -> str | None:
        get = getattr(self._platform, "get", None)
        if not callable(get):
            return None
        rec = get(name)
        if not isinstance(rec, dict):
            return None
        if rec.get("status") != "published":
            return None
        content = rec.get("content")
        return str(content) if content is not None else None

    def render(self, name: str, /, **vars: str) -> str:
        content = self._published_content(name)
        if content is not None:
            return content.format(**vars)
        if self._fallback is not None:
            return self._fallback.render(name, **vars)
        raise FileNotFoundError(f"prompt not found: {name}")
