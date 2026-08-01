"""Exercise the P2-A console API path without printing request content or tokens."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from jose import jwt

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


def _events(body: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for block in body.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                out.append(json.loads(line[6:]))
    return out


def main() -> int:
    from fastapi.testclient import TestClient
    from testing.app_factory import create_test_app

    logging.getLogger("httpx").setLevel(logging.WARNING)
    os.environ.update(
        {
            "AGENTBRIDGE_FAKE_RUNTIME": "1",
            "KNOWLEDGE_BACKEND": "fake",
            "AUTH_REQUIRED": "true",
            "AUTH_DEV_STUB": "false",
            "OIDC_JWT_SECRET": "p2a-console-test-secret",
        }
    )
    token = jwt.encode(
        {
            "sub": "p2a-console",
            "tenant_id": "p2a-console",
            "roles": ["admin"],
            "permissions": ["admin:audit"],
        },
        os.environ["OIDC_JWT_SECRET"],
        algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(create_test_app()) as client:
        stream = client.post(
            "/chat/stream",
            headers=headers,
            json={"query": "p2a console validation", "thread_id": "p2a-console", "route": "echo"},
        )
        events = _events(stream.text)
        if stream.status_code != 200 or not events:
            print("P2-A console path: failed")
            return 1
        run_id = str(events[0]["run_id"])
        replay = client.get(f"/runs/{run_id}/events", headers=headers)
        audit = client.get("/admin/audit/export", headers=headers)
    if replay.status_code != 200 or audit.status_code != 200:
        print("P2-A console path: failed")
        return 1
    print(
        "P2-A console path: "
        f"stream={stream.status_code}; replay={len(replay.json())}; audit={len(audit.text.splitlines())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
