"""Run the redacted P2-A lifecycle and delivery-failure matrix."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "packages/core/tests/application/test_event_log_emit_order.py",
    "packages/core/tests/application/test_lifecycle_projection.py",
    "apps/api/tests/test_chat_cancel.py",
    "apps/api/tests/test_threads_and_events.py",
    "apps/api/tests/test_work_order_ops.py",
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
        print("P2-A lifecycle matrix: failed")
        return result.returncode
    summary = next(
        (line.strip() for line in result.stdout.splitlines() if " passed" in line),
        "passed",
    )
    print(f"P2-A lifecycle matrix: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
