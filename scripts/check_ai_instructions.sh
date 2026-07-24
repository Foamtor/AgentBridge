#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
required=(
  docs/ai-instructions/00-project-overview.md
  docs/ai-instructions/01-architecture-rules.md
  docs/ai-instructions/02-domain-development.md
  docs/ai-instructions/03-common-tasks.md
  docs/ai-instructions/04-testing.md
)
for f in "${required[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "missing: $f" >&2
    exit 1
  fi
done
echo "ai-instructions: ok"
