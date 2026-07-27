# 底座 R-A 实施设计（langchain_pg 真检索）

> **状态：** 已确认（brainstorm 2026-07-27）  
> **日期：** 2026-07-27  
> **归属：** 设计三类之 **① 底座**（见 [design-tracks.md](../../design-tracks.md)）  
> **上位 Spec：** [platform-final-spec.md](./2026-07-27-platform-final-spec.md)  
> **收敛依据：** [scheme-convergence.md](./2026-07-27-scheme-convergence.md)  
> **实施计划：** 待本设计评审通过后由 writing-plans 产出（对齐 [Plan6](../plans/2026-07-27-plan6-rag-production.md) R-A）

---

## 0. 一句话

先把底座知识插座从「只有 Fake」升级到 **可切换的 `langchain_pg` 真检索**，citation 对齐统一 `KnowledgeHit`；入库 HTTP 与拆 Port 留给 R-B。

---

## 1. 目标与边界

### 1.1 做（R-A）

| 项 | 说明 |
|----|------|
| `KnowledgeHit` | 统一命中结构；Fake / langchain_pg 均按此返回 |
| `LangchainPgRetriever` | PG + pgvector + 进程外 HTTP Embedding（本机 TEI） |
| 配置切换 | `KNOWLEDGE_BACKEND=fake\|langchain_pg`，仅在 `lifespan` 组装 |
| `demo_rag` citation | `x.bridge.citation` 字段对齐 `KnowledgeHit` |
| 种子数据 | 继续用 **Retriever.ingest**（测试/脚本）；**不**暴露 HTTP `/ingest` |
| 租户隔离 | 检索/入库强制 `tenant_id`；跨租户不可见 |
| 架构门禁 | domains / application 禁止 import 引擎包（如 `langchain_postgres`） |

### 1.2 不做（排期延后，不是砍需求）

| 项 | 留给 |
|----|------|
| HTTP `/ingest`、入库任务 status API | **R-B** |
| 独立 `KnowledgeIngest` Port | **R-B** |
| `external` / `product` 后端 | **R-C** |
| AI 控制台 UI | **② 管理轨**（Plan7） |
| 仓库内嵌 TEI / 本地假 Embedding | 本期用集成方本机 TEI；CI 主路径仍 Fake |

### 1.3 拍板记录（brainstorm）

| 决策 | 选择 |
|------|------|
| 第一期范围 | R-A 先落地验收，再进 R-B |
| Embedding | 只接进程外 HTTP（OpenAI 兼容）；对接本机 TEI |
| 真链路验收 | 手动：`compose --profile rag` + 自备 TEI + `EMBED_*` |
| 种子数据 | 保留 Retriever.ingest；不上 HTTP `/ingest` |
| 落地路径 | 最小增量（方案 1）：契约 + 适配器 + lifespan + demo_rag |

---

## 2. 架构与数据流

```text
业务插件 demo_rag
    │ 只调 Retriever Port（similarity_search / ingest）
    ▼
packages/core
  ├─ KnowledgeHit
  ├─ FakeRetriever              ← 默认 / CI
  └─ LangchainPgRetriever       ← KNOWLEDGE_BACKEND=langchain_pg
         │
         ├─► PostgreSQL + pgvector（compose --profile rag）
         └─► 本机 TEI（EMBED_API_BASE，OpenAI 兼容）
    ▲
    │ 唯一 new 适配器处
apps/api/lifespan.py
```

| 组件 | 职责 |
|------|------|
| `KnowledgeHit` | 所有后端检索结果的统一形状；citation 按它填 |
| `Retriever` | `similarity_search` + `ingest`（R-A 不拆入库 Port） |
| `FakeRetriever` | 内存；返回对齐 `KnowledgeHit` |
| `LangchainPgRetriever` | TEI 向量化 → 写入/检索 PG；强制 `tenant_id` |
| `lifespan` | 按配置组装并注入 Run metadata（如 `retriever`） |
| `demo_rag` | 发 `x.bridge.citation`，使用 `chunk_id`/`doc_id`/… |

依赖方向遵守：`application` 不 import `adapters`；domains 不 import 引擎 SDK；适配器只在 `lifespan` 构造。

---

## 3. 契约

### 3.1 `KnowledgeHit`

| 字段 | 必填 | 说明 |
|------|------|------|
| `chunk_id` | 是 | 分块 ID |
| `doc_id` | 是 | 文档 ID |
| `text` | 是 | 摘录正文 |
| `tenant_id` | 是 | 必须与请求租户一致 |
| `score` | 否 | 相关分 |
| `metadata` | 否 | 扩展；不得替代租户隔离 |
| `section_anchor` | 否 | R-A 可空 |
| `jump_url` | 否 | R-A 可空 |

### 3.2 检索参数（R-A 最小子集）

- `query`、`tenant_id`（必填）、`k`（**默认 5**，与 platform-final-spec 一致；调用方可传更小值，如 demo_rag 用 3）
- `tier` / `corpus_ids` / `include_scores`：**R-B 起**；R-A 可忽略

### 3.3 Citation

- SSE：`type: "x.bridge.citation"`，`data.citations[]` 元素对齐 `KnowledgeHit`
- 可多 `route` 字段标识插件（如 `demo_rag`）
- 旧演示字段 `id` **不再作为真源**

### 3.4 兼容映射

Fake/种子若仍带旧 `id`：适配层映射为 `chunk_id`；缺 `doc_id` 时可用 `doc_id=chunk_id`，避免演示断掉。

---

## 4. 配置

| 变量 | 含义 | 档 |
|------|------|-----|
| `KNOWLEDGE_BACKEND` | `fake`（默认）\| `langchain_pg` | B 启动项 |
| `KB_DSN` | 空则回退 `PG_DSN` | B |
| `EMBED_API_BASE` | TEI / OpenAI 兼容 Base URL | B |
| `EMBED_MODEL` | 模型名 | B |
| `EMBED_DIMENSIONS` | 向量维数，须与模型一致 | B |
| `EMBED_API_KEY` | 可选；TEI 常可空 | C |

切换后端：改配置 + 安装对应 extra（如 `rag` / `rag-langchain`），**不改**业务插件代码。

Compose：已有 `postgres-rag`（`pgvector/pgvector:pg16`，`--profile rag`）。R-A **不**在仓库内嵌 TEI 服务。

---

## 5. 错误与降级（R-A 最小）

| 情况 | 行为 |
|------|------|
| 缺 `tenant_id` / 跨租户 | Port/适配器失败或空结果；绝不返回他租户文档 |
| TEI / PG 不可用 | 检索返回空命中 + 可观测（日志/降级标记）；**不**因知识挂掉把整次对话打成 500 |
| 未装 extra 却选 `langchain_pg` | 启动失败，错误信息写清需安装的 extra |
| `ingest` | 仅进程内/测试种子；无对外 HTTP |

`/ready` 对 embedding 的细状态可按现有 ready 机制扩展，对齐 [platform-final-spec §11.1](./2026-07-27-platform-final-spec.md)；R-A 至少保证「不可用时不 500」。

---

## 6. 测试与验收

### 6.1 自动化（默认 CI）

- Fake + `KnowledgeHit` 形状
- `demo_rag` citation 含 `chunk_id` / `doc_id`
- Fake 跨租户隔离
- 架构门禁：domains / application 不依赖引擎包
- 主路径 **不**强制 pgvector / TEI

### 6.2 手测（集成方本机）

1. `docker compose --profile rag up -d`
2. 本机 TEI 可用；配置 `EMBED_*` + `KNOWLEDGE_BACKEND=langchain_pg`
3. 经 `Retriever.ingest` 种子若干文档
4. 能检索到；租户 A 看不到租户 B
5. SSE 含合法 `x.bridge.citation`

### 6.3 成功标准

1. `KNOWLEDGE_BACKEND=fake`：主路径绿；citation 字段对齐  
2. 本机 TEI + pgvector：真检索 + 跨租户隔离  
3. 切换后端只改配置与 extra，不改 `demo_rag` 业务逻辑  

---

## 7. 与既有文档关系

| 文档 | 关系 |
|------|------|
| platform-final-spec | 最终形态；本设计是其 **R-A 切片** |
| rag-production-design / Plan6 | 多阶段地图；本设计钉死 R-A 实施边界 |
| knowledge-base / deploy | 实现后对齐 `EMBED_*` 与两档体验说明 |
| R-B / R-C / Plan7 | 明确不在本设计范围 |

---

## 8. 下一步

1. 用户评审本文件  
2. 通过后 → **writing-plans** 产出可执行任务清单（对齐 Plan6 T1–T8）  
3. 再开实施会话按计划编码  
