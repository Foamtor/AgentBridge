"""Validate the public, redacted P2-A release-validation record."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_EVIDENCE = _ROOT / "docs" / "release-validation" / "p2a-runtime-security-rag-console.md"
_REQUIRED_MARKERS = (
    "# P2-A",
    "## 环境与版本",
    "## 命令与结果",
    "## 任务状态",
    "## 阻塞项与已知限制",
    "## 复核",
    "## 脱敏规则",
    "P2-B",
    "A0",
    "A1",
    "A2",
    "A3",
    "A4",
    "A5",
    "A6",
    "A7",
    "A8",
    "A9",
)
_SECRET_PATTERNS = (
    r"postgres(?:ql)?://",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"bearer\s+eyJ[\w.-]+",
    r"(?:api[_-]?key|password)\s*[:=]\s*\S+",
)


def validate_evidence(text: str) -> list[str]:
    """Return redacted validation errors without including document values."""

    errors = [
        f"missing-required-marker:{marker}"
        for marker in _REQUIRED_MARKERS
        if marker not in text
    ]
    lowered = text.lower()
    for pattern in _SECRET_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            errors.append("disallowed-secret-pattern")
    return errors


def main() -> int:
    if not _EVIDENCE.is_file():
        print("P2-A evidence invalid: missing document")
        return 1
    errors = validate_evidence(_EVIDENCE.read_text(encoding="utf-8"))
    if errors:
        print(f"P2-A evidence invalid: {len(errors)} checks failed")
        return 1
    print("P2-A evidence valid: task-record structure and redaction checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
