#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "Starting API on http://127.0.0.1:8000 ..."
python -m uvicorn main:app --app-dir apps/api --reload --port 8000 &
API_PID=$!
echo "$API_PID" > .agent-base-api.pid

if command -v pnpm >/dev/null 2>&1; then
  echo "Starting web on http://127.0.0.1:5173 ..."
  (cd apps/web && pnpm dev) &
  echo $! > .agent-base-web.pid
elif command -v npm >/dev/null 2>&1; then
  echo "Starting web on http://127.0.0.1:5173 ..."
  (cd apps/web && npm run dev) &
  echo $! > .agent-base-web.pid
else
  echo "Skip web: pnpm/npm not found"
fi

echo "API pid=$API_PID"
wait "$API_PID"
