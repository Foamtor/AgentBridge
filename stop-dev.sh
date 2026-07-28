#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
# Current names
if [[ -f .agentbridge-api.pid ]]; then kill "$(cat .agentbridge-api.pid)" 2>/dev/null || true; rm -f .agentbridge-api.pid; fi
if [[ -f .agentbridge-web.pid ]]; then kill "$(cat .agentbridge-web.pid)" 2>/dev/null || true; rm -f .agentbridge-web.pid; fi
# Legacy rename leftovers
if [[ -f .agent-base-api.pid ]]; then kill "$(cat .agent-base-api.pid)" 2>/dev/null || true; rm -f .agent-base-api.pid; fi
if [[ -f .agent-base-web.pid ]]; then kill "$(cat .agent-base-web.pid)" 2>/dev/null || true; rm -f .agent-base-web.pid; fi
echo "stop-dev: done"
