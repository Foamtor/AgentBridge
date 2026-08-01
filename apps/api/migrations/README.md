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

## Knowledge (R-A)

1. Start Postgres with pgvector: `docker compose --profile rag up -d`
2. Apply `003_knowledge_pgvector.sql` (vector size must match `EMBED_DIMENSIONS`; default **1024**)
3. Install `pip install -e "apps/api[rag]"` and set `KNOWLEDGE_BACKEND=langchain_pg` + `EMBED_*`
4. Seed: `python scripts/ingest_demo_rag.py`

R-A does **not** call `init_vectorstore_table`; DDL is owned by this migration.

## Approval execution (P1)

Apply `004_approval_execution.sql` before setting `APPROVAL_STORE_BACKEND=postgres`.
Apply `005_work_order_ops.sql`, then `006_approval_hardening.sql` and
`007_work_order_demo_tenant.sql` in that order for the P1 golden case.
The `memory` backend remains suitable for tests and local demonstrations; the
PostgreSQL backend is required for restart-safe approval execution.
