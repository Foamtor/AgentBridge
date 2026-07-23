#!/usr/bin/env bash
set -euo pipefail
API="${API_BASE:-http://127.0.0.1:8000}"

echo "== health =="
curl -sf "$API/health" | grep -q '"status":"ok"'

TID="t-smoke-$(date +%s)"
echo "== stream =="
curl -sf -N -X POST "$API/chat/stream" \
  -H 'Content-Type: application/json' \
  -d "{\"query\":\"smoke\",\"thread_id\":\"$TID\",\"route\":\"echo\"}" \
  | head -c 2000 | grep -q '"type": "start\|"type":"start'

echo "== cancel idle =="
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/chat/cancel" \
  -H 'Content-Type: application/json' \
  -d "{\"thread_id\":\"t-smoke-missing\"}")
test "$code" = "404"

echo "== thread busy 409 =="
# hold is hard in pure curl; skip if API down — rely on pytest for lock hold
echo "smoke_echo: ok (stream+cancel paths exercised; 409 covered in pytest)"
