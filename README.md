# AgentBridge

[简体中文](README.zh-CN.md) · [Documentation](docs/INDEX.md) · [Architecture rules](AGENTS.md)

[![CI](https://github.com/Foamtor/AgentBridge/actions/workflows/ci.yml/badge.svg)](https://github.com/Foamtor/AgentBridge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](packages/core/pyproject.toml)

## Build governed AI workflows on top of your existing business systems

AgentBridge is a self-hosted, AI-readable foundation for Vibe Coding business tools. It lets an AI and your developers write the business-specific `domain` and `tools`, while the platform owns the difficult shared behavior: JSON/SSE contracts, session lifecycle, permissions, approvals, audit, and RAG ports.

It is a source-first foundation—not a hosted Studio, not a finished industry application, and not a package that can understand your business without customization.

<!-- A real work-order golden-case screenshot is added once the Compose UI flow lands. -->

## Why AgentBridge

Adding AI to an existing ERP, support, device, or operations system tends to repeat the same risky work:

- streaming output that remains ordered and replayable;
- tenant and permission context that tools cannot bypass;
- a human approval boundary before a write takes effect;
- a safe way to bring retrieval into a real business flow;
- a clear boundary between reusable platform code and customer-specific code.

AgentBridge makes these shared concerns platform responsibilities. Your business code stays in a plugin-like domain.

| You and your coding AI build | AgentBridge provides |
| --- | --- |
| Business flow, tools, permissions, structured results | JSON/SSE envelopes, lifecycle, cancellation, session locking |
| Queries, forms, charts, ledger data | Tool visibility filtering and invoke-time authorization |
| Business-specific adapters and UI consumers | Approval, audit, tenant context, RAG/DataSource ports |

## How it works

```text
Existing business system
        │
        ├── AI-written domain / tools / tests
        │
        ▼
AgentBridge API ── JSON + SSE ── Integration Console / your client
        │
        ├── permissions · audit · approval · lifecycle
        └── DataSource / Retriever / LLM Gateway ports
```

The architecture deliberately keeps business names out of `packages/core`. Adapters are assembled in `apps/api/lifespan.py`; domains consume injected ports and return business fragments instead of pushing SSE directly.

## Golden use case: work-order operations

[`work_order_ops`](apps/api/domains/work_order_ops/) is the reference implementation for a realistic business loop. Its bundled data is synthetic and redacted.

1. Query tenant-scoped work orders.
2. Return a structured list, an ECharts option, and knowledge citations.
3. Prepare a work-order and ledger draft with an assignee.
4. Require a human decision before creating the work order and ledger.
5. Produce an idempotent creation result after approval.

The console renderer is a reference for consuming extension events such as `x.work_order_ops.list`, `x.work_order_ops.chart`, `x.bridge.citation`, and `x.bridge.approval_required`. It is not a customer-facing work-order system.

## Quick start

The v0.1.0 primary path is a single Compose command:

```bash
docker compose up --build
```

Then open the integration console and choose `work_order_ops`. The default stack uses an offline model stub, fake knowledge, redacted demo data, and a development tenant; it needs no model key, external RAG service, or IdP. Detailed ports, reset behavior, and local development alternatives are in the [quick-start guide](docs/guide/02-quickstart.md).

> The full-stack Compose stack is part of the v0.1.0 release work. Until it lands, use the existing [local development guide](docs/guide/02-quickstart.md).

## Build with AI

Open this repository at its root and give your coding assistant this prompt:

```text
You are modifying AgentBridge. Read AGENTS.md first, then
docs/ai-instructions/00-project-overview.md and 01-architecture-rules.md.
For a new business capability, read 02-domain-development.md and use
apps/api/domains/work_order_ops as a realistic reference, without copying its
business name into packages/core.

Define inputs, permissions, structured results, approval/idempotency needs,
and tests before implementation. Do not create adapters inside a domain and do
not emit SSE directly from a domain. Keep unauthorized tools out of the model
tool list and rely on invoke-time authorization as well.

My task: <describe the domain or tool to add>
```

More ready-to-copy recipes—for read tools, list/chart/ledger output, and approval-gated writes—are in [AI coding instructions](docs/ai-instructions/05-ai-coding.md).

## Capabilities

| Area | Included foundation |
| --- | --- |
| Conversation runtime | FastAPI, LangGraph, stable SSE, cancellation, per-thread coordination |
| Governance | Tenant context, tool-list filtering, invoke-time policy checks, audit, approval |
| Business integration | Domain registry, DataSource and Retriever ports, structured extension events |
| Knowledge | Fake, pgvector, external, and optional read-only RAG-Agent-compatible retrieval backends |
| Developer experience | Integration console, TypeScript SDK, AI-readable rules, golden domain |

## Repository map

```text
packages/core/       reusable lifecycle, ports, protocols, and adapters
apps/api/            FastAPI host, composition root, routes, and domains
apps/api/domains/    business plugins; start with _scaffold or work_order_ops
apps/web/            integration/debug console, not a customer business UI
packages/sdk/        TypeScript client
docs/                guides, contracts, architecture, and AI instructions
```

## Documentation

- [Get started](docs/guide/02-quickstart.md)
- [Understand the concepts](docs/guide/03-concepts.md)
- [Create your first domain](docs/guide/04-first-plugin.md)
- [JSON and SSE contracts](docs/contracts.md)
- [Architecture and non-negotiable rules](AGENTS.md)
- [Full product architecture](docs/00-AgentBridge完整方案.md)
- [v0.1.0 release scope](docs/superpowers/specs/2026-08-01-p3a-open-source-release-readiness-design.md)

## Status and limitations

AgentBridge is preparing its **v0.1.0 Technical Preview**. The preview is intended for developers and teams building an AI layer over an existing system.

- The default demo is deliberately offline and uses redacted data.
- Real LLMs, external RAG, OIDC, multi-instance operation, deployment migration, backup/recovery, and production hardening remain opt-in or deferred work.
- The optional RAG-Agent integration is read-only and mapped to a fixed demonstration tenant; it is not required by the default stack.
- No PyPI, npm, GHCR, signed-image, or enterprise supply-chain release is part of this preview.

See the [release plan](docs/release-plan.md) for the boundary and deferred P2-B production validation.

## Contributing and security

Contributions should preserve the architecture rules and use only redacted example data. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) once the v0.1.0 community files land.

## License

MIT. See [LICENSE](LICENSE).
