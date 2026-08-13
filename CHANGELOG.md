# Changelog

All notable public changes are recorded here.

## v0.1.0 — Technical Preview

- Source-first Vibe Coding foundation with AI-readable architecture rules.
- Business domain/tool model with stable JSON/SSE contracts, permissions, audit, and approval lifecycle.
- `work_order_ops` golden case for synthetic work-order queries, ECharts data, citations, ledger preview, and approval-gated creation.
- One Docker Compose development stack for Web, API, and PostgreSQL/pgvector without external model credentials.
- English and Simplified Chinese project homepages, contribution guidance, and security reporting guidance.

### Known limits

- Production deployment drills, migration/recovery, concrete IdP integration, and multi-instance validation are post-1.0 hardening work; they are not single-node 1.0 release gates.
- Real LLMs and external RAG are opt-in integrations; the default demo runs offline.
- This preview does not publish PyPI, npm, GHCR, signed images, or supply-chain artifacts.
