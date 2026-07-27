# 底座 R-A 实施设计（langchain_pg 真检索）

> **状态：** 设计定稿 · 实施计划已就绪（2026-07-27）  
> **日期：** 2026-07-27  
> **归属：** 设计三类之 **① 底座**（见 [design-tracks.md](../../design-tracks.md)）  
> **上位 Spec：** [platform-final-spec.md](./2026-07-27-platform-final-spec.md)  
> **收敛依据：** [scheme-convergence.md](./2026-07-27-scheme-convergence.md)  
> **多后端地图：** [rag-production-design.md](./2026-07-27-rag-production-design.md)  
> **实施计划：** [../plans/2026-07-27-platform-ra.md](../plans/2026-07-27-platform-ra.md)（对齐 [Plan6](../plans/2026-07-27-plan6-rag-production.md) R-A / T1–T8）

---

## 0. 一句话

把知识插座从「只有 Fake」升级到 **可切换的 `langchain_pg` 真检索**，统一 `KnowledgeHit` 与 citation；HTTP 入库留给 R-B。

---

## 1. 目标与边界

### 1.1 做（R-A）

| 项 | 说明 |
|----|------|
| `KnowledgeHit` | 核心库 TypedDict（或等价）；Fake / langchain_pg 均返回该形状 |
| Port 钉死 | 真源方法名 **`similarity_search`** + **`ingest`**（见 §3） |
| `LangchainPgRetriever` | PG + pgvector + 进程外 HTTP Embedding（本机 TEI） |
| 配置切换 | `KNOWLEDGE_BACKEND=fake\|langchain_pg`，只在 `lifespan` 组装 |
| `demo_rag` citation | `citations[]` 对齐 `KnowledgeHit`；信封级 `route` |
| 种子数据 | `Retriever.ingest` + 更新 `scripts/ingest_demo_rag.py`；**无** HTTP `/ingest` |
| 租户隔离 | 空 `tenant_id` **直接失败**；查询强制过滤；跨租户不可见 |
| extra | 钉死名 **`rag`**（见 §4） |
| 架构门禁 | domains / application 禁止 import `langchain_postgres` 等引擎包 |
| 文档 | 实现后对齐 `knowledge-base.md` / `deploy.md` / `.env.example` 中 R-A 相关项 |

### 1.2 不做（排期延后，不是砍需求）

| 项 | 留给 |
|----|------|
| HTTP `/ingest`、入库任务 status API | **R-B** |
| 独立 `KnowledgeIngest` Port | **R-B** |
| `RetrievalOptions.tier` / `corpus_ids` / `include_scores` | **R-B** |
| 混合检索（hybrid / RRF） | **R-B 或其后**；R-A 只做向量相似度 |
| `external` / `product` | **R-C** |
| AI 控制台 UI / `GET /admin/config` | **②**（Plan7）；R-A 不拦路 |
| 仓库内嵌 TEI、本地假 Embedding、强制 CI 真检索 job | 本期手测；CI 主路径仍 Fake |

### 1.3 拍板记录（brainstorm）

| 决策 | 选择 |
|------|------|
| 第一期范围 | R-A 先落地验收，再进 R-B |
| Embedding | 只接进程外 HTTP（OpenAI 兼容）；对接本机 TEI |
| 真链路验收 | 手动：`compose --profile rag` + 自备 TEI + `EMBED_*` |
| 种子数据 | 保留 Retriever.ingest；不上 HTTP `/ingest` |
| 落地路径 | 最小增量：契约 + 适配器 + lifespan + demo_rag + 种子脚本 |

---

## 2. 架构与数据流

```text
业务插件 demo_rag
    │ 只调 Retriever.similarity_search / ingest
    ▼
packages/core
  ├─ protocol：KnowledgeHit（TypedDict）
  ├─ ports：Retriever
  ├─ FakeRetriever                 ← 默认 / CI
  └─ LangchainPgRetriever          ← KNOWLEDGE_BACKEND=langchain_pg
         │
         ├─► PostgreSQL + pgvector（compose --profile rag）
         └─► 本机 TEI（EMBED_API_BASE，OpenAI 兼容 /v1/embeddings）
    ▲
    │ 唯一 new 适配器处
apps/api/lifespan.py  → 注入 ctx.metadata["retriever"]
```

| 组件 | 职责 |
|------|------|
| `KnowledgeHit` | 统一命中形状；citation 按它填 |
| `Retriever` | `similarity_search` + `ingest` |
| `FakeRetriever` | 内存；返回/规范化为 `KnowledgeHit` |
| `LangchainPgRetriever` | TEI 向量化 → 写入/检索 PG；强制租户 |
| `lifespan` | 读 Settings 组装；缺依赖则启动失败（见 §5） |
| `demo_rag` | 发 `x.bridge.citation` |

依赖方向：`application` 不 import `adapters`；domains 不 import 引擎 SDK；适配器只在 `lifespan` 构造。

### 2.1 租户怎么隔离（钉死）

| 规则 | 行为 |
|------|------|
| `tenant_id` 为空 / 仅空白 | **抛错**（如 `ValueError`），不静默当 `default` |
| `ingest` | 每条文档 metadata（或等价字段）写入 `tenant_id`；与参数不一致则拒绝 |
| `similarity_search` | 查询侧 **必须**按 `tenant_id` 过滤（langchain 元数据过滤或等价）；不得依赖「调用方自觉」 |
| 结果校验 | 返回前丢弃/断言 `hit.tenant_id == 请求租户`（防适配器漏过滤） |

**集合策略（R-A）：** 使用 **单一向量集合/表** + 文档 metadata 上的 `tenant_id` 过滤。  
不按租户拆多个 collection（避免运维爆炸）。表/schema 落点：优先 `knowledge` schema（或 langchain-postgres 默认表 + 明确前缀）；与 checkpointer 表互不覆盖；迁移 SQL 放 `apps/api/migrations/`，幂等。

### 2.2 与 checkpointer 双驱动

与 [platform-final-spec §4.4.1](./2026-07-27-platform-final-spec.md) 一致：checkpointer 可用现有 `psycopg`；知识侧跟 `langchain-postgres` 官方异步路径（如 asyncpg）。**分池**、均在 `lifespan` 创建/关闭；默认 DSN 共用 `PG_DSN`，知识可用 `KB_DSN` 覆盖。

---

## 3. 契约

### 3.1 `KnowledgeHit`

| 字段 | 必填 | 说明 |
|------|------|------|
| `chunk_id` | 是 | 分块 ID |
| `doc_id` | 是 | 文档 ID |
| `text` | 是 | 摘录正文 |
| `tenant_id` | 是 | 必须与请求租户一致 |
| `score` | 否 | 相关分；R-A 有则填，无则 `null`/省略 |
| `metadata` | 否 | 扩展；**不得**替代租户隔离 |
| `section_anchor` | 否 | R-A 可省略 |
| `jump_url` | 否 | R-A 可省略 |

实现：放在 `packages/core` 的 protocol（TypedDict）；Port 标注返回 `list[KnowledgeHit]`（运行时仍是 dict 亦可，但类型与单测按字段断言）。

### 3.2 `Retriever` Port（R-A 真源）

```text
similarity_search(query, *, tenant_id: str, k: int = 5) -> list[KnowledgeHit]
ingest(docs, *, tenant_id: str) -> int
```

- **不**在 R-A 新增并行真源方法名 `search`（`knowledge-base.md` 里若写 `search`，实现后改为与 Port 一致）。
- `k` 默认 **5**（platform-final-spec）；`demo_rag` 可传 `k=3`。

### 3.3 `ingest` 文档形状（种子入参）

每条至少：

| 字段 | 说明 |
|------|------|
| `text` | 必填 |
| `chunk_id` | 推荐；若只有旧字段 `id`，规范化为 `chunk_id` |
| `doc_id` | 推荐；缺省则 `doc_id = chunk_id` |
| `tenant_id` | 可省略（用参数 `tenant_id` 写入）；若文档自带则必须与参数一致 |
| 其它 | 进 `metadata` |

### 3.4 Citation

信封（与现 `demo_rag` 一致，避免破坏客户端）：

```json
{
  "type": "x.bridge.citation",
  "data": {
    "route": "demo_rag",
    "citations": [ /* KnowledgeHit 字段 */ ]
  }
}
```

- `route` 在 **`data` 上**，不要求塞进每条 citation。
- `citations[]` 元素对齐 `KnowledgeHit`；旧字段 `id` **不再作为真源**（可短期兼容映射，见下）。

### 3.5 兼容映射

| 入参/旧数据 | 规范化 |
|-------------|--------|
| `id` 无 `chunk_id` | `chunk_id = id` |
| 无 `doc_id` | `doc_id = chunk_id` |
| 有 `tenant_id` 且与参数冲突 | 拒绝该条或整次 ingest 失败（实现选一种并单测钉死；推荐 **整次失败**） |

---

## 4. 配置与依赖

| 变量 | 含义 | 档 |
|------|------|-----|
| `KNOWLEDGE_BACKEND` | `fake`（默认）\| `langchain_pg` | B |
| `KB_DSN` | 空则回退 `PG_DSN` | B |
| `EMBED_API_BASE` | TEI / OpenAI 兼容 Base（须能打到 `/v1/embeddings` 或文档写明的路径约定） | B |
| `EMBED_MODEL` | 模型名 | B |
| `EMBED_DIMENSIONS` | 向量维数，与模型一致 | B |
| `EMBED_API_KEY` | 可选；本机 TEI 常可空 | C |

**extra 名钉死：`rag`**（安装示例：`pip install -e "apps/api[rag]"` 或 core 侧等价；以 pyproject 落地为准）。  
内容：`langchain-postgres`、OpenAI 兼容 embeddings 客户端、必要驱动。  
文档里的 `rag-langchain` 视为同义别名，**实现只维护一个 extra 名 `rag`**，避免双真源。

`KNOWLEDGE_BACKEND=langchain_pg` 时启动前校验：

1. `rag` extra 可 import  
2. `EMBED_API_BASE`、`EMBED_MODEL`、`EMBED_DIMENSIONS` 已配置  
3. DSN 可用（`KB_DSN` 或 `PG_DSN`）  

任一失败 → **进程启动失败**，错误信息写清缺什么。

Compose：已有 `postgres-rag`（`pgvector/pgvector:pg16`，`--profile rag`）。R-A **不**在仓库内嵌 TEI。

---

## 5. 错误与降级

| 情况 | 行为 |
|------|------|
| `tenant_id` 空 | **抛错**（不默认为 `default`） |
| 跨租户 | 过滤后为空列表；不得泄露 |
| 运行中 TEI / PG 短暂失败 | `similarity_search` → **空列表** + 日志（可观测）；**不**把整次 chat 打成 500 |
| `langchain_pg` 启动缺配置/extra | **启动失败**（见 §4） |
| `ingest` | 仅进程内/脚本；无 HTTP；失败向上抛给脚本/测试 |

`/ready` 细状态（embedding healthy/degraded/…）对齐 platform-final-spec §11.1：**R-A 建议扩展**，但门禁是「检索失败不 500」；完整 status 矩阵可与 ready 插件一并做，不阻塞 Fake 路径。

---

## 6. 代码落点（实施地图）

| 区域 | 变更 |
|------|------|
| `packages/core/.../protocol/` | 新增 `KnowledgeHit` |
| `packages/core/.../ports/retriever.py` | 签名/返回类型对齐；`k` 默认 5 |
| `packages/core/.../adapters/fake_retriever.py` | 规范化输出；跨租户单测 |
| `packages/core/.../adapters/` | 新增 `langchain_pg_retriever.py`（或等价名） |
| `packages/core/pyproject.toml` 与/或 `apps/api/pyproject.toml` | optional-deps `rag` |
| `apps/api/config/settings.py` | `knowledge_backend`、`kb_dsn`、`embed_*` |
| `apps/api/lifespan.py` | 按 backend 组装；注入 metadata |
| `apps/api/domains/demo_rag/graph.py` | citation 字段；勿再依赖裸 `id` |
| `apps/api/migrations/` | knowledge / pgvector 相关幂等 SQL（若库表需显式建） |
| `scripts/ingest_demo_rag.py` | 走统一字段；可指向 Fake 或真后端 |
| 架构门禁 | import-linter / 扫描规则 |
| 文档 | `knowledge-base.md`、`deploy.md`、`.env.example` |

---

## 7. 测试与验收

### 7.1 自动化（默认 CI）

- Fake：`KnowledgeHit` 必填字段  
- Fake：跨租户隔离；空 `tenant_id` 抛错  
- `demo_rag`：SSE citation 含 `chunk_id` / `doc_id` / `tenant_id`  
- 架构门禁：domains / application 不依赖引擎包  
- **不**强制 pgvector / TEI

### 7.2 手测（本机 TEI）

1. `docker compose --profile rag up -d`  
2. TEI 可用；`.env`：`KNOWLEDGE_BACKEND=langchain_pg` + `EMBED_*` + DSN  
3. `scripts/ingest_demo_rag.py`（或等价）种子  
4. `demo_rag` 能搜到；租户 A 看不到 B  
5. SSE 含合法 `x.bridge.citation`  

### 7.3 成功标准

1. Fake 主路径绿；citation 字段对齐  
2. 本机 TEI + pgvector：真检索 + 跨租户  
3. 切换后端只改配置与 `rag` extra，不改 `demo_rag` 检索业务逻辑  

---

## 8. 与既有文档关系

| 文档 | 关系 |
|------|------|
| platform-final-spec | 最终形态；本文件是 **R-A 切片**（冲突时：契约字段以 final + 本文件钉死项为准） |
| rag-production-design / Plan6 | 多阶段地图；本文件收窄 R-A |
| knowledge-base / deploy | 实现后改成与 Port 方法名、`rag` extra、手测步骤一致 |
| R-B / R-C / Plan7 | 明确不在范围 |

---

## 9. 下一步

1. 按 [platform-ra 实施计划](../plans/2026-07-27-platform-ra.md) 执行 Task 1–8  
2. R-A 手测通过后再开 R-B（`/ingest`）  

---

## 10. 修订说明（相对初稿）

| 问题 | 修订 |
|------|------|
| Port 方法名与 knowledge-base 的 `search` 不一致 | 钉死 `similarity_search` |
| 缺 `tenant_id`「失败或空结果」双解 | 空 → **抛错**；跨租户 → 空列表 |
| extra `rag` / `rag-langchain` 双名 | 只维护 **`rag`** |
| 未写租户隔离实现方式 | 单集合 + metadata 过滤 + 返回前校验 |
| 未写表/schema、双驱动 | 对齐 platform §4.4 |
| citation `route` 位置含糊 | 钉在 `data.route`（信封） |
| `ingest` 入参形状未定义 | 新增 §3.3 |
| 混合检索是否进 R-A | **不进**；仅向量相似 |
| 缺启动校验与代码落点 | 新增 §4 校验、§6 落点 |
| 种子脚本未点名 | 明确更新 `scripts/ingest_demo_rag.py` |
