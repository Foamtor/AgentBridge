#!/usr/bin/env python3
"""Run golden policy evals. Exit 1 on any mismatch."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from agentbridge_core.adapters.role_policy import RolePolicyEngine
from agentbridge_core.protocol.context import RunContext

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = ROOT / "evals" / "golden"


def _run_file(path: Path, policy: RolePolicyEngine) -> list[str]:
    failures: list[str] = []
    payload = json.loads(path.read_text(encoding="utf-8"))
    suite = payload.get("name") or path.stem
    for case in payload.get("cases") or []:
        cid = case.get("id") or "?"
        ctx = RunContext(
            roles=list(case.get("roles") or []),
            permissions=list(case.get("permissions") or []),
        )
        got = policy.decide(
            ctx=ctx,
            action=str(case.get("action") or ""),
            resource=dict(case.get("resource") or {}),
        )
        expect = str(case.get("expect") or "")
        if got != expect:
            failures.append(f"{suite}/{cid}: expect={expect!r} got={got!r}")
    return failures


def main() -> int:
    if not GOLDEN_DIR.is_dir():
        print(f"missing golden dir: {GOLDEN_DIR}", file=sys.stderr)
        return 1
    files = sorted(GOLDEN_DIR.glob("*.json"))
    if not files:
        print(f"no golden files in {GOLDEN_DIR}", file=sys.stderr)
        return 1
    policy = RolePolicyEngine()
    failures: list[str] = []
    for path in files:
        failures.extend(_run_file(path, policy))
    if failures:
        print("EVAL FAILED:", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1
    print(f"ok: {len(files)} suite(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
