"""Bring up a disposable Compose stack and verify the golden flow."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import socket
import subprocess
import time
import uuid
from pathlib import Path
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


ROOT = Path(__file__).resolve().parents[1]


def request_json(url: str, *, payload: dict | None = None, opener=None) -> tuple[int, str]:
    body = None if payload is None else json.dumps(payload).encode()
    request = Request(url, data=body, headers={"Content-Type": "application/json"} if body else {})
    open_url = opener.open if opener else urlopen
    with open_url(request, timeout=10) as response:  # noqa: S310 - local Compose URL
        return response.status, response.read().decode()


def events(body: str) -> list[dict]:
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def run(command: list[str], env: dict[str, str]) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def initial_password(compose: list[str], env: dict[str, str]) -> str:
    output = subprocess.check_output([*compose, "logs", "api"], cwd=ROOT, env=env, text=True)
    marker = "AGENTBRIDGE_INITIAL_ADMIN_PASSWORD username=admin password="
    for line in output.splitlines():
        if marker in line:
            return line.split(marker, 1)[1].strip()
    raise RuntimeError("initial administrator password was not emitted by the API")


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
        password = initial_password(compose, env)
        cookies = http.cookiejar.CookieJar()
        opener = build_opener(HTTPCookieProcessor(cookies))
        _, session = request_json(
            f"{base}/auth/login", payload={"username": "admin", "password": password}, opener=opener
        )
        if json.loads(session).get("status") != "password_change_required":
            raise RuntimeError("initial administrator login did not require a password change")
        _, session = request_json(
            f"{base}/auth/change-password",
            payload={"current_password": password, "new_password": "AgentBridge smoke password 2026!"},
            opener=opener,
        )
        if json.loads(session).get("status") != "authenticated":
            raise RuntimeError("administrator password change did not authenticate the session")
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
        body = request_json(f"{base}/chat/stream", payload={"query": "show work orders as a pie chart", "thread_id": "smoke-list", "route": "work_order_ops"}, opener=opener)[1]
        types = {event["type"] for event in events(body)}
        required = {"x.work_order_ops.list", "x.work_order_ops.chart", "done"}
        if not required <= types:
            raise RuntimeError(f"golden read flow missing events: {required - types}")
        if args.golden_case:
            draft = request_json(f"{base}/chat/stream", payload={"query": "create a synthetic work order", "thread_id": "smoke-draft", "route": "work_order_ops", "extra": {"work_order_draft": {"title": "Synthetic smoke follow-up", "priority": "medium", "assignee_id": "assignee-dev-a", "ledger_summary": "Synthetic Compose smoke ledger"}}}, opener=opener)[1]
            approval = next(event for event in events(draft) if event["type"] == "x.bridge.approval_required")
            approval_id = str(approval["data"]["approval_id"])
            _, result = request_json(f"{base}/approvals/{approval_id}", payload={"decision": "approve"}, opener=opener)
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
