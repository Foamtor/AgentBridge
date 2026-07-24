"""Token-budget ContextManager (tiktoken optional via encoder inject)."""

from __future__ import annotations

from typing import Any


def _content_of(msg: Any) -> str:
    if isinstance(msg, dict):
        return str(msg.get("content") or "")
    return str(getattr(msg, "content", "") or "")


def _role_of(msg: Any) -> str:
    if isinstance(msg, dict):
        return str(msg.get("role") or "")
    return str(getattr(msg, "type", getattr(msg, "role", "")) or "")


class TokenBudgetContextManager:
    """Keep newest messages under ``budget_tokens``; never drop leading system msgs.

    Pass a tiktoken ``Encoding`` as ``encoder`` when the optional extra is installed.
    Default estimates tokens as ``ceil(len/chars_per_token)``.
    """

    def __init__(
        self,
        *,
        chars_per_token: float = 4.0,
        encoder: Any | None = None,
    ) -> None:
        self._chars_per_token = max(chars_per_token, 0.1)
        self._encoding = encoder

    def count_tokens(self, text: str) -> int:
        if self._encoding is not None:
            return len(self._encoding.encode(text))
        if not text:
            return 0
        return max(1, int(len(text) / self._chars_per_token))

    def build_messages(
        self, messages: list[Any], *, budget_tokens: int
    ) -> list[Any]:
        if budget_tokens <= 0 or not messages:
            return []
        system: list[Any] = []
        rest: list[Any] = []
        for m in messages:
            if _role_of(m) in {"system", "SystemMessage"}:
                system.append(m)
            else:
                rest.append(m)

        used = sum(self.count_tokens(_content_of(m)) for m in system)
        selected_rest: list[Any] = []
        for m in reversed(rest):
            cost = self.count_tokens(_content_of(m))
            if used + cost > budget_tokens:
                if not selected_rest and used < budget_tokens:
                    # Keep at least the newest turn when nothing else fits fully.
                    selected_rest.append(m)
                break
            selected_rest.append(m)
            used += cost
        selected_rest.reverse()
        return [*system, *selected_rest]
