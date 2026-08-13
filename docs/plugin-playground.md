# Plugin Playground

`/playground` is the daily development surface for a domain plugin. `/` remains the short, fixed `work_order_ops` Quick Verify path for a first installation.

## What it provides

- P0: editable route/thread/model/request JSON, real-time SSE, cancel, 409 concurrency check, request replay, curl copy, timing, tool trace, contract checks, and JSONL export.
- P1: tenant-scoped thread/run browser, turn selection, PostgreSQL-persisted event replay, run/thread/trace filtering, and run-level structured evidence.
- P2: PostgreSQL-persisted generic run annotations and badcases, plus route/tool/contract aggregate diagnostics. The console never queries PostgreSQL directly.

The run inspector is intentionally protocol-first. It projects stable events, extension events, timing, and tools from committed event data; it does not contain a `work_order_ops` dependency. A domain may expose its own structured renderer through extension events.

Compose configures `OBSERVABILITY_STORE_BACKEND=postgres` and a PostgreSQL checkpointer. This is the required acceptance path for P1/P2: restart the API and replay the same run, thread messages, JSONL evidence, and annotations. `OBSERVABILITY_STORE_BACKEND=memory` is only for isolated tests or an explicitly selected offline demo; it is not acceptance evidence.

`RAG_Agent`'s `/api/v1/chat` is an application-facing SSE API, not an OpenAI-compatible model endpoint or the `external` retriever protocol. To reuse its configured upstream model, configure AgentBridge separately with the same OpenAI-compatible provider values. To reuse its knowledge, either expose `POST /v1/retrieve` plus `GET /v1/health` with the external Retriever contract, or use the read-only `rag_agent_pg` backend with a reachable RAG-Agent PostgreSQL instance. Do not label either integration as verified until its service and database health checks pass.

## Reference case modes

The Verification Workbench offers two `work_order_ops` modes:

- **Fake demo** is deterministic and offline. It is the default for first-run verification.
- **Real model** sends the query to the configured model, then lets that model select only the already-authorized read tools. Tool execution still uses tenant-scoped DataSource/Retriever ports; write actions still require the normal approval path.

Configure the real mode in `.env` and restart the API/Compose stack:

```dotenv
LLM_MODE=openai_compatible
LLM_API_BASE=https://your-openai-compatible-endpoint/v1
LLM_MODEL=your-model-name
LLM_API_KEY=replace-me
ENABLE_DATA_SOURCE=true
DATA_SOURCE_DSN=postgresql://user:password@host:5432/your_business_database
```

For real knowledge results, also configure `KNOWLEDGE_BACKEND=external` or `langchain_pg`. If real mode is selected while the service is still in Fake mode, the run fails explicitly with `real_model_not_configured`; it never silently claims a real-model result.

For operator-managed model switching, configure `MODEL_CONFIG_ENCRYPTION_KEY`
outside PostgreSQL and use the `/models` admin page. When the API runs directly
from the source tree, a local administrator can generate this key in the page;
the API writes it to the repository `.env`, and must then be restarted. Enter an
alias, OpenAI-compatible API base, model name, and key. The model key is stored
as authenticated ciphertext in PostgreSQL and is never returned to the browser.
Compose mounts the repository `.env` into the API, so the same page flow works
there when the file exists before startup. Other container deployments should
mount a persistent environment file or use a secret manager. The Verification Workbench and Playground only receive
enabled aliases; Fake remains available independently.
