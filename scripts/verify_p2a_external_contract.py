"""Run the redacted P2-A external RAG contract matrix."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "apps/api/tests/test_external_rag_retriever.py",
    "apps/api/tests/test_ingest_api.py",
    "apps/api/tests/test_demo_rag.py",
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
        print("P2-A external RAG matrix: failed")
        return result.returncode
    summary = next(
        (line.strip() for line in result.stdout.splitlines() if " passed" in line),
        "passed",
    )
    print(f"P2-A external RAG matrix: {summary}; contract-tested; vendor-live deferred to P2-B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
