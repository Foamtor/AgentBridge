# 知识库与 RAG 使用说明

> **归属：** 底座①（多知识后端）。总纲见 [design-tracks.md](./design-tracks.md)。  
> **R-A 设计：** [superpowers/specs/2026-07-27-platform-ra-design.md](./superpowers/specs/2026-07-27-platform-ra-design.md)  
> **R-A 实施计划：** [superpowers/plans/2026-07-27-platform-ra.md](./superpowers/plans/2026-07-27-platform-ra.md)  
> **多后端地图：** [superpowers/specs/2026-07-27-rag-production-design.md](./superpowers/specs/2026-07-27-rag-production-design.md)

---

## 这是什么

底座把「搜知识」做成可替换插座（`Retriever` Port）。业务插件只调 Port，不绑引擎。

| 客户情况 | 配置 |
|----------|------|
| 本地 / CI | `KNOWLEDGE_BACKEND=fake`（默认） |
| 真检索（R-A） | `langchain_pg` + 本机 TEI + pgvector |
| 客户自有 RAG | `external`（**R-C**，未实现） |
| 自研重引擎 | `product`（**R-C+**，未实现） |

**租户：** 每次检索/种子入库必须带非空 `tenant_id`；空值会报错，不会默默变成 `default`。

---

## 当前能力（R-A）

| 能力 | 说明 |
|------|------|
| Fake | 内存检索；CI 默认 |
| `langchain_pg` | PG + pgvector + HTTP Embedding（OpenAI 兼容 / TEI） |
| 示例插件 | `demo_rag` → SSE `x.bridge.citation`（字段对齐 `KnowledgeHit`） |
| 种子脚本 | `scripts/ingest_demo_rag.py`（**无** HTTP `/ingest`，入库 API 属 R-B） |

安装真后端依赖：

```bash
pip install -e "apps/api[rag]"
```

```env
KNOWLEDGE_BACKEND=langchain_pg
# KB_DSN=                 # 空则用 PG_DSN
EMBED_API_BASE=http://127.0.0.1:8080/v1
EMBED_MODEL=your-tei-model
EMBED_DIMENSIONS=1024
```

手测步骤：

1. `docker compose --profile rag up -d`
2. 执行 `apps/api/migrations/003_knowledge_pgvector.sql`（`vector(N)` 与 `EMBED_DIMENSIONS` 一致）
3. 配好 `EMBED_*`，跑 `python scripts/ingest_demo_rag.py`
4. 启动 API，对 `demo_rag` 发对话，应看到带 `chunk_id` / `doc_id` 的 citation；跨租户搜不到

---

## 业务插件怎么接

1. `retriever = ctx.metadata["retriever"]`
2. `await retriever.similarity_search(query, tenant_id=ctx.tenant_id, k=5)`
3. 打出 `x.bridge.citation`（`data.route` + `data.citations[]`）
4. **禁止** 在插件内 import `langchain_postgres` 等引擎包

见 [add-a-domain.md](./add-a-domain.md)。

---

## 常见问题

**Q：Port 方法名是 search 吗？**  
不是。真源是 **`similarity_search`** / **`ingest`**。

**Q：HTTP `/ingest` 呢？**  
R-B。R-A 只用进程内 `Retriever.ingest` / 种子脚本。

**Q：客户已有 RAG？**  
用 `external`（R-C）；协议见 [external-rag-protocol](./superpowers/specs/2026-07-27-external-rag-protocol.md)。
