"""Bring up a disposable v0.1 Compose stack and verify the golden flow."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


def request_json(url: str, *, payload: dict | None = None) -> tuple[int, str]:
    body = None if payload is None else json.dumps(payload).encode()
    request = Request(url, data=body, headers={"Content-Type": "application/json"} if body else {})
    with urlopen(request, timeout=10) as response:  # noqa: S310 - local Compose URL
        return response.status, response.read().decode()


def events(body: str) -> list[dict]:
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def run(command: list[str], env: dict[str, str]) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def available_port() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return str(listener.getsockname()[1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden-case", action="store_true")
    parser.add_argument("--remove-demo-volume", action="store_true")
    args = parser.parse_args()
    project = f"agentbridge_smoke_{uuid.uuid4().hex[:8]}"
    port = available_port()
    env = {**os.environ, "COMPOSE_PROJECT_NAME": project, "WEB_PORT": port}
    compose = ["docker", "compose"]
    try:
        run([*compose, "config", "--quiet"], env)
        run([*compose, "up", "--build", "--detach", "--wait"], env)
        base = f"http://127.0.0.1:{port}/api"
        deadline = time.monotonic() + 45
        while True:
            try:
                status, _ = request_json(f"{base}/ready")
                if status == 200:
                    break
            except Exception:  # noqa: BLE001
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("Compose API did not become ready")
            time.sleep(1)
        request_json(f"http://127.0.0.1:{port}/")
        body = request_json(f"{base}/chat/stream", payload={"query": "show work orders as a pie chart", "thread_id": "smoke-list", "route": "work_order_ops"})[1]
        types = {event["type"] for event in events(body)}
        required = {"x.work_order_ops.list", "x.work_order_ops.chart", "done"}
        if not required <= types:
            raise RuntimeError(f"golden read flow missing events: {required - types}")
        if args.golden_case:
            draft = request_json(f"{base}/chat/stream", payload={"query": "create a synthetic work order", "thread_id": "smoke-draft", "route": "work_order_ops", "extra": {"work_order_draft": {"title": "Synthetic smoke follow-up", "priority": "medium", "assignee_id": "assignee-dev-a", "ledger_summary": "Synthetic Compose smoke ledger"}}})[1]
            approval = next(event for event in events(draft) if event["type"] == "x.bridge.approval_required")
            approval_id = str(approval["data"]["approval_id"])
            _, result = request_json(f"{base}/approvals/{approval_id}", payload={"decision": "approve"})
            if json.loads(result).get("approval", {}).get("status") != "succeeded":
                raise RuntimeError("golden approval did not succeed")
        print("Compose smoke passed")
        return 0
    finally:
        down = [*compose, "down"]
        if args.remove_demo_volume:
            down.append("--volumes")
        subprocess.run(down, cwd=ROOT, env=env, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
