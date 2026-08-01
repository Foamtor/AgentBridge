"""Run the redacted P2-A authorization and audit matrix."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "apps/api/tests/test_demo_readonly_policy.py",
    "apps/api/tests/test_work_order_ops.py",
    "apps/api/tests/test_approvals_api.py",
    "apps/api/tests/test_audit_export.py",
)


def main() -> int:
    env = dict(os.environ)
    env["KNOWLEDGE_BACKEND"] = "fake"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *TARGETS, "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        print("P2-A security matrix: failed")
        return result.returncode
    summary = next(
        (line.strip() for line in result.stdout.splitlines() if " passed" in line),
        "passed",
    )
    print(f"P2-A security matrix: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
