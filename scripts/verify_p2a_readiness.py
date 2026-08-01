"""Run the redacted P2-A single-node readiness matrix."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "apps/api/tests/test_rate_limit.py",
    "apps/api/tests/test_ready.py",
    "apps/api/tests/test_knowledge_status_provider.py",
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
        print("P2-A readiness matrix: failed")
        return result.returncode
    summary = next(
        (line.strip() for line in result.stdout.splitlines() if " passed" in line),
        "passed",
    )
    print(f"P2-A readiness matrix: {summary}; single-node only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
