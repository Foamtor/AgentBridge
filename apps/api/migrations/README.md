Checkpointer / schema migrations.

| File | Purpose |
|------|---------|
| `001_checkpointer.sql` | LangGraph checkpointer tables |
| `002_demo_readonly.sql` | Demo DataSource sample tables |
| `003_knowledge_pgvector.sql` | R-A knowledge schema + `kb_chunks` (needs **pgvector**) |
| `004_approval_execution.sql` | Durable, platform-generic approval action records |
| `005_work_order_ops.sql` | Synthetic tenant-scoped golden-case business data |
| `006_approval_hardening.sql` | Approval fencing, sequence, expiry and terminal projection fields |
| `007_work_order_demo_tenant.sql` | Synthetic `rag-agent-demo` work-order reference data |
| `008_v01_demo.sql` | Synthetic `dev` tenant data for the default v0.1.0 Compose demo |

## Knowledge (R-A)

1. Start Postgres with pgvector: `docker compose --profile rag up -d`
2. Apply `003_knowledge_pgvector.sql` for the P2-A reference embedding model (`BAAI/bge-m3`, 512 dimensions). Changing an existing collection to a model with another dimension requires re-embedding; that upgrade procedure is part of P2-B.
3. Install `pip install -e "apps/api[rag]"` and set `KNOWLEDGE_BACKEND=langchain_pg` + `EMBED_*`
4. Seed: `python scripts/ingest_demo_rag.py`

R-A does **not** call `init_vectorstore_table`; DDL is owned by this migration.

## Approval execution (P1)

Apply `004_approval_execution.sql` before setting `APPROVAL_STORE_BACKEND=postgres`.
Apply `005_work_order_ops.sql`, then `006_approval_hardening.sql` and
`007_work_order_demo_tenant.sql` in that order for the P1 golden case.
The `memory` backend remains suitable for tests and local demonstrations; the
PostgreSQL backend is required for restart-safe approval execution.

## Default Compose demo

The root `docker-compose.yml` mounts all numbered SQL files into a **new**
PostgreSQL volume. `008_v01_demo.sql` supplies the `dev` tenant used when
authentication is disabled. Existing volumes are intentionally not migrated by
the entrypoint; remove only the AgentBridge demo volume when you explicitly
want to reset synthetic data.
