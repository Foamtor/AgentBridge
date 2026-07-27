"""Regex phone masker with reversible token_map (run-scoped)."""

from __future__ import annotations

import re

_PHONE_RE = re.compile(r"(?<!\d)(1\d{10})(?!\d)")


class RegexDataMasker:
    """Mask CN mobile numbers as ``[PHONE_n]`` tokens stored in token_map."""

    def mask(self, text: str, token_map: dict[str, str]) -> str:
        def _repl(m: re.Match[str]) -> str:
            raw = m.group(1)
            for tok, val in token_map.items():
                if val == raw:
                    return tok
            tok = f"[PHONE_{len(token_map) + 1}]"
            token_map[tok] = raw
            return tok

        return _PHONE_RE.sub(_repl, text)

    def unmask(self, text: str, token_map: dict[str, str]) -> str:
        out = text
        # Longer tokens first to avoid partial replaces.
        for tok in sorted(token_map.keys(), key=len, reverse=True):
            out = out.replace(tok, token_map[tok])
        return out
