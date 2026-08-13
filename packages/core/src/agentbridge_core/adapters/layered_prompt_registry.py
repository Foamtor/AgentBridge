"""Platform-first PromptRegistry with optional file fallback."""

from __future__ import annotations

import inspect
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

    async def resolve(self, name: str) -> dict[str, Any] | None:
        """Resolve a published platform prompt, with an optional file fallback."""
        get = getattr(self._platform, "get", None)
        if callable(get):
            rec = get(name)
            if inspect.isawaitable(rec):
                rec = await rec
            if isinstance(rec, dict) and rec.get("status") == "published":
                content = rec.get("content")
                if content is not None:
                    return {
                        "name": name,
                        "content": str(content),
                        "source": "platform",
                        "version": int(rec.get("version") or 0),
                    }
        if self._fallback is None:
            return None
        try:
            content = self._fallback.render(name)
        except FileNotFoundError:
            return None
        return {"name": name, "content": content, "source": "file", "version": 0}

    async def render_async(self, name: str, /, **vars: str) -> str:
        resolved = await self.resolve(name)
        if resolved is None:
            raise FileNotFoundError(f"prompt not found: {name}")
        return str(resolved["content"]).format(**vars)

    def render(self, name: str, /, **vars: str) -> str:
        content = self._published_content(name)
        if content is not None:
            return content.format(**vars)
        if self._fallback is not None:
            return self._fallback.render(name, **vars)
        raise FileNotFoundError(f"prompt not found: {name}")
