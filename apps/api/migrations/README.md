Checkpointer / schema migrations.

| File | Purpose |
|------|---------|
| `001_checkpointer.sql` | LangGraph checkpointer tables |
| `002_demo_readonly.sql` | Demo DataSource sample tables |
| `003_knowledge_pgvector.sql` | R-A knowledge schema + `kb_chunks` (needs **pgvector**) |

## Knowledge (R-A)

1. Start Postgres with pgvector: `docker compose --profile rag up -d`
2. Apply `003_knowledge_pgvector.sql` (vector size must match `EMBED_DIMENSIONS`; default **1024**)
3. Install `pip install -e "apps/api[rag]"` and set `KNOWLEDGE_BACKEND=langchain_pg` + `EMBED_*`
4. Seed: `python scripts/ingest_demo_rag.py`

R-A does **not** call `init_vectorstore_table`; DDL is owned by this migration.
