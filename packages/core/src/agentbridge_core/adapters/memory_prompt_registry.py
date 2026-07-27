"""In-memory prompt store for admin CRUD."""

from __future__ import annotations

from typing import Any


class MemoryPromptRegistry:
    def __init__(self) -> None:
        self._drafts: dict[str, dict[str, Any]] = {}
        self._published: dict[str, dict[str, Any]] = {}

    def list_names(self) -> list[str]:
        return sorted(set(self._drafts) | set(self._published))

    def get(self, name: str) -> dict[str, Any] | None:
        if name in self._drafts:
            rec = dict(self._drafts[name])
            rec.setdefault("status", "draft")
            return rec
        if name in self._published:
            rec = dict(self._published[name])
            rec["status"] = "published"
            return rec
        return None

    def put(self, name: str, *, content: str) -> dict[str, Any]:
        rec = {
            "name": name,
            "content": content,
            "status": "draft",
            "version": int(self._drafts.get(name, {}).get("version", 0)) + 1,
        }
        self._drafts[name] = rec
        return dict(rec)

    def publish(self, name: str) -> dict[str, Any]:
        draft = self._drafts.get(name) or self._published.get(name)
        if draft is None:
            raise KeyError(name)
        rec = dict(draft)
        rec["status"] = "published"
        version = int(rec.get("version") or 0) + 1
        rec["version"] = version
        self._published[name] = rec
        self._drafts.pop(name, None)
        return rec

    def render(self, name: str, /, **vars: str) -> str:
        rec = self.get(name)
        if rec is None:
            raise FileNotFoundError(f"prompt not found: {name}")
        return str(rec["content"]).format(**vars)
