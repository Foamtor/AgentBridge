"""Lightweight release-document checks; keep links and entry points honest."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    ROOT / "README.md",
    ROOT / "README.zh-CN.md",
    ROOT / "AGENTS.md",
    ROOT / "CLAUDE.md",
    ROOT / "docs" / "INDEX.md",
    ROOT / "docs" / "superpowers" / "README.md",
    ROOT / "docs" / "superpowers" / "specs" / "2026-08-01-p3a-open-source-release-readiness-design.md",
    ROOT / "docs" / "superpowers" / "plans" / "2026-08-01-p3a-open-source-release-preparation.md",
)
PUBLIC_DOCS = (
    ROOT / "README.md",
    ROOT / "README.zh-CN.md",
    ROOT / "docs" / "INDEX.md",
    ROOT / "docs" / "release-plan.md",
    ROOT / "docs" / "roadmap.md",
    ROOT / "docs" / "superpowers" / "README.md",
    ROOT / "docs" / "superpowers" / "plans" / "README.md",
)
LINK = re.compile(r"\[[^]]+\]\(([^)#]+)(?:#[^)]+)?\)")


def main() -> int:
    errors: list[str] = []
    for path in REQUIRED:
        if not path.is_file():
            errors.append(f"missing required release document: {path.relative_to(ROOT)}")

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    if agents.replace("`CLAUDE.md`", "`PEER.md`") != claude.replace("`AGENTS.md`", "`PEER.md`"):
        errors.append("AGENTS.md and CLAUDE.md body differs")

    for path in PUBLIC_DOCS:
        text = path.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            if target.startswith(("https://", "http://", "mailto:")):
                continue
            if not (path.parent / target).resolve().exists():
                errors.append(f"broken local link: {path.relative_to(ROOT)} -> {target}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    for marker, text in (("README English", readme), ("README Chinese", chinese)):
        for required in ("docker compose up --build", "work_order_ops", "AGENTS.md"):
            if required not in text:
                errors.append(f"{marker} missing release marker: {required}")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("release documentation checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
