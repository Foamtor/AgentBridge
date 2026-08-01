# 知识库与 RAG 使用说明

> **归属：** 底座①（多知识后端）。  
> **R-A 设计（历史切片，部分表述已过时）：** [superpowers/specs/2026-07-27-platform-ra-design.md](./superpowers/specs/2026-07-27-platform-ra-design.md) — 其中「无 HTTP `/ingest`」已被后续实现取代，**以本文与代码为准**  
> **R-A 实施计划：** [superpowers/plans/2026-07-27-platform-ra.md](./superpowers/plans/2026-07-27-platform-ra.md)  
> **相关分期计划：** [superpowers/plans/2026-07-27-plan6-rag-production.md](./superpowers/plans/2026-07-27-plan6-rag-production.md)  
> 冲突时以 [完整方案](./00-AgentBridge完整方案.md) 与代码为准。

---

## 这是什么

底座把「搜知识」做成可替换插座（`Retriever` Port）。业务插件只调 Port，不绑引擎。

| 客户情况 | 配置 |
|----------|------|
| 本地 / CI | `KNOWLEDGE_BACKEND=fake`（默认） |
| 真检索（平台库） | `langchain_pg` + 本机 TEI + pgvector |
| 客户自有 RAG | `external` + `KB_EXTERNAL_BASE_URL`（HTTP 检索适配器，由 lifespan 组装） |
| 自研重引擎 | `product`（规划中，勿当已交付） |

**租户：** 每次检索/种子入库必须带非空 `tenant_id`；空值会报错，不会默默变成 `default`。

---

## 当前能力

| 能力 | 说明 |
|------|------|
| Fake | 内存检索；CI 默认 |
| `langchain_pg` | PG + pgvector + HTTP Embedding（OpenAI 兼容 / TEI） |
| `external` | 外部 HTTP 检索（由 lifespan 组装；ingest 可能 501） |
| `rag_agent_pg` | 已完成真实验收的只读 RAG-Agent PostgreSQL 接入；仅固定演示租户可检索 |
| 示例插件 | `demo_rag` → SSE `x.bridge.citation`（字段对齐 `KnowledgeHit`） |
| HTTP `/ingest` | 已提供（需 `knowledge:write`）；后端不支持时返回 501 |
| 种子脚本 | `scripts/ingest_demo_rag.py`（进程内入库，便于本地灌 demo） |

安装真后端依赖：

```bash
pip install -e "apps/api[rag]"
```

`rag_agent_pg` 不会摄取或修改 RAG-Agent 数据。使用只读账号，并可运行
`python scripts/verify_rag_agent_readonly.py` 完成无正文、无凭据输出的验收探针。

```env
KNOWLEDGE_BACKEND=langchain_pg
# KB_DSN=                 # 空则用 PG_DSN
EMBED_API_BASE=http://127.0.0.1:8080/v1
EMBED_MODEL=your-tei-model
EMBED_DIMENSIONS=512
```

手测步骤：

1. `docker compose --profile rag up -d`
2. 执行 `apps/api/migrations/003_knowledge_pgvector.sql`。P2-A 参考模型为 `BAAI/bge-m3`（512 维）；既有集合更换模型维度时必须重建并重嵌入，升级流程留在 P2-B。
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
已有 `POST /ingest`（需写权限）。`external` 等后端若不支持入库会 501；也可用种子脚本做本地灌数。

**Q：客户已有 RAG？**  
用 `KNOWLEDGE_BACKEND=external` + `KB_EXTERNAL_BASE_URL`。对接字段以代码适配器与 `.env.example` 为准；历史协议稿若缺失，以完整方案与实现为准。
# Work-order RAG reference

The `work_order_ops` golden case combines tenant-scoped business data with SOP
and FAQ retrieval. With `KB_EXTERNAL_FAILURE_POLICY=fail_run`, external
timeouts and 5xx responses are dependency failures and must reach a stable
error path; only a successful `200` response with `hits: []` means “no
knowledge match.” See
[`apps/api/domains/work_order_ops/README.md`](../apps/api/domains/work_order_ops/README.md).
