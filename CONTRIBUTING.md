# Contributing to AgentBridge

AgentBridge is a source-first foundation for building governed AI workflows over existing business systems.

## Before you code

1. Read [AGENTS.md](AGENTS.md); its MUST rules are non-negotiable.
2. Read the relevant files in [docs/ai-instructions](docs/ai-instructions/00-project-overview.md).
3. Start a new business capability from `apps/api/domains/_scaffold/`; use `work_order_ops` only as a realistic pattern reference.

Keep business names out of `packages/core`, assemble adapters only in the host composition root, and return domain extensions through `OUTBOUND_EXTENSIONS_KEY` rather than pushing SSE from a domain.

## Tests

Run the relevant tests while developing. Before opening a pull request, run:

```bash
python -m pytest packages/core/tests apps/api/tests -q
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
```

For Web changes, also run `npm test` and `npm run build` in `apps/web` with Node 22.14.

## Data and security

Never commit credentials, DSNs, production logs, customer data, embeddings, database volumes, or screenshots containing sensitive information. Demonstrations and tests must use synthetic or redacted data.

## Pull requests

Explain the user-visible behavior, tests run, and any architecture boundary touched. If a change alters JSON/SSE contracts, permissions, approval semantics, or tenant boundaries, link the relevant contract and describe compatibility.
