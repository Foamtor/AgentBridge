# AgentBridge 底座最终形态 Spec（开源可发布级）

> **状态：** 历史架构设计；实现状态与当前首发范围以 [v0.1.0 Spec](./2026-08-01-p3a-open-source-release-readiness-design.md) 为准。
>
> **日期：** 2026-07-27  
> **读者：** 集成开发者 · 平台管理员 · 开源贡献者  
> **归属：** 历史底座设计记录。
>
> **拍板依据：** 已收敛到根目录完整方案与当前首发 Spec。
>
> **冲突时：** 契约以 [contracts.md](../../contracts.md) + `protocol/events.py` 为准；排期以本 Spec + roadmap 为准

---

## 0. 一句话

AgentBridge 是给传统业务系统接入 AI 的**底座**：流式对话、权限审计、工具联动、数据问答、可换知识后端。  
客户业务页面自己做；框架提供 **AI 控制台**（调试与配置可见性）。行业场景用 **业务插件**扩展。

**生产数据库：统一 PostgreSQL（含 pgvector）。开发可用内存。不用 SQLite 做主路径。**

---

## 1. 目标与边界

### 1.1 目标

| 能力 | 说明 |
|------|------|
| 对话接入 | HTTP/SSE/SDK，稳定事件契约 |
| 工具联动 | 权限双检；可接业务 API |
| 数据问答 | DataSource 白名单查数（非开放 NL2SQL） |
| 知识问答 | Retriever 可换后端 + citation |
| 治理 | 审计、审批、脱敏、限流、回放 |

### 1.2 不做

| 不做 | 原因 |
|------|------|
| 客户业务前端（一张图、政务工作台） | 客户自建；框架不替代 |
| 企业 IAM / 账号中心 | 接客户 OIDC/JWT |
| 云 Studio / 拖拽造 Agent | 超出底座范围 |
| 研究型任意群聊 | 多 Agent = 单流 supervisor/subgraph |
| SQLite 作为生产库 | 无 pgvector、弱并发、与 async 主路径不合 |

### 1.3 三类分工

```text
客户业务前端（不做）
        │  HTTP / SSE / SDK
        ▼
┌────────────── ① 底座（本 Spec）──────────────┐
│ 对话 · 权限 · 审计 · Gateway · DataSource     │
│ Retriever / KnowledgeIngest（多后端）         │
│ 审批 · 多机（可选 Redis）                     │
└───────────┬──────────────────▲───────────────┘
            │ 注册使用           │ 配置/观测 API
            ▼                    │
   ③ 业务插件              ② AI 控制台
   domains/*               apps/web（C0+）
```

---

## 2. 核心架构

### 2.1 代码分层与依赖方向

```text
apps/web  ──HTTP──►  apps/api（routes / lifespan / domains）
                              │
                              │ lifespan：唯一 new 适配器处
                              ▼
                     packages/core
                     ├─ application（RunLifecycle）──禁止 import adapters
                     ├─ ports（接口）
                     ├─ protocol（事件/上下文）
                     ├─ adapters（LangGraph / PG / Fake…）
                     └─ registry（图/工具注册）

domains/* ──register──► registry
domains 禁止 import：具体 RAG SDK、adapters、EventSink
```

### 2.2 LangGraph 的位置

- **主运行时：** LangGraph + langchain-core（工具协议）  
- **不是：** LangGraph Platform / LangSmith Agent Server 的托管替代  
- **防腐：** `LangGraphRuntime` 把框架流映射为对外 Event；业务插件写图，不碰 SSE 细节

### 2.3 组装根

- **唯一**允许大量 `new` 具体适配器的地方：`apps/api/lifespan.py`  
- 配置来源：环境变量（启动项/密钥）+ 后续 ConfigProvider（可热配，C2+）

### 2.4 必须遵守（MUST）

1. `application` 禁止 import `adapters`  
2. 业务插件不持有 `EventSink`  
3. `core/src` 不出现业务插件名  
4. 适配器只在 lifespan 构造  
5. 无权限工具不进 LLM tool list  
6. 跨租户在 Port 层失败  
7. `LLM_BACKEND=gateway` 后模型须经 Gateway  

---

## 3. 运行时契约

### 3.1 兼容承诺

| 规则 | 说明 |
|------|------|
| 真源 | [contracts.md](../../contracts.md) + `packages/core/.../protocol/events.py` |
| SSE 事件类型 | **只增不删**；废弃类型保留至少两个次要版本 |
| HTTP 路径 | 破坏性变更须升主版本或提供并存期 |
| `KnowledgeHit` | 字段只增不删；未知字段忽略 |

### 3.2 核心 HTTP（底座必有）

| 方法 | 路径 | 状态 |
|------|------|------|
| GET | `/health` | ✅ |
| GET | `/ready` | ✅ |
| GET | `/metrics` | ✅ |
| POST | `/chat/stream` | ✅ |
| POST | `/chat/cancel` | ✅ |
| GET | `/threads`、`/threads/{id}/messages` | ✅ |
| GET | `/runs/{id}`、`/runs/{id}/events` | ✅ |
| GET | `/runs` | 📋 未实现（管理列表用 `/admin/runs`） |
| GET/POST | `/approvals/*` | ✅ |
| GET | `/admin/overview`、`/admin/domains`、`/admin/config` | ✅ C0 |
| GET | `/admin/tools`、`/admin/runs` | ✅ C1 |
| PUT | `/admin/config/{key}`、`/prompts/*` | ✅ C2 |
| GET | `/admin/usage/tokens` | ✅ C3 |
| GET | `/admin/knowledge/status` | ✅ C4（路由已有；provider 未注入时 503） |
| GET | `/admin/audit/export` | ✅ |
| POST | `/ingest` | 📋 M11 |

### 3.3 统一命中模型 `KnowledgeHit`

所有知识后端映射到此结构（业务插件只认这个）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `chunk_id` | string | 是 | 分块/节点 ID |
| `doc_id` | string | 是 | 文档 ID |
| `text` | string | 是 | 摘录正文 |
| `tenant_id` | string | 是 | 必须与请求租户一致 |
| `score` | number \| null | 否 | 相关分 |
| `metadata` | object | 否 | 扩展；不得替代 tenant 隔离 |
| `section_anchor` | string \| null | 否 | 章节锚点 |
| `jump_url` | string \| null | 否 | 只读跳转（R-C） |

检索选项 `RetrievalOptions`：

| 字段 | 默认 | 阶段 | 说明 |
|------|------|------|------|
| `k` | 5 | **R-A** | 返回条数 |
| `tenant_id` | — | **R-A** | 必填；Port 签名级 |
| `tier` | `standard` | R-B | `fast` \| `standard` \| `deep` |
| `corpus_ids` | `[]` | R-B | 可选语料过滤 |
| `include_scores` | false | R-B | 是否带 score |

> **R-A 最小子集：** 仅 `k` + `tenant_id`。`tier` / `corpus_ids` / `include_scores` 在 R-B 起支持；R-A 可忽略。

### 3.4 Citation

SSE：`type: "x.bridge.citation"`，`data.citations[]` 元素对齐 `KnowledgeHit`（可多 `route` 字段标识插件）。

### 3.5 稳定语义

| 场景 | 行为 |
|------|------|
| 同 thread 忙 | HTTP **409**，`code=thread_busy` |
| 取消 | 流内 `cancel_requested` → `cancelled` |
| 审批等待 | RunStore=`awaiting_approval`，**释放**会话锁；续跑同 `run_id` |

---

## 4. 数据库最终策略

### 4.1 原则

| 场景 | 方案 |
|------|------|
| 本地开发 / CI | **内存**：`USE_MEMORY_CHECKPOINTER=true` + `KNOWLEDGE_BACKEND=fake` |
| 单机生产 | **一个 PostgreSQL 实例**（会话、事件、Run、知识、入库任务） |
| 多机 | PG + **Redis**（锁/限流，M9） |
| **禁止** | SQLite 作生产或知识主路径 |

### 4.2 版本基线（发布时钉死在 deploy）

| 组件 | 最低要求 | 当前 compose |
|------|----------|--------------|
| PostgreSQL | **≥ 16** | `postgres:16-alpine` |
| pgvector | **≥ 0.7**（扩展启用） | R-A 起改用带 pgvector 的镜像（如 `pgvector/pgvector:pg16`） |
| Redis | ≥ 7（多机） | `redis:7-alpine` |
| Python | ≥ 3.12 | — |

### 4.3 Schema 策略

同一 PG 实例，**逻辑隔离**：

| 用途 | 建议 |
|------|------|
| Checkpointer / 事件 / 消息 / Run | 默认 `public`（或现有表） |
| 知识向量 / 文档元数据 / 入库任务 | schema **`knowledge`**（或表前缀 `kb_`） |
| 业务只读库 | 独立 DSN（`DATA_SOURCE_DSN`），可与平台同实例不同库 |
| 官方查数样板表（如 `demo_sales`） | 落在 **DataSource DSN**（默认可与平台同实例）；**不**进 `knowledge` schema |

R-A 落地时：迁移脚本创建 `knowledge` schema（或 `kb_*` 表），与 checkpointer 表不互相覆盖。  
`demo_sales` 等样板表：独立迁移文件（如 `apps/api/migrations/demo_sales.sql`），对 **`DATA_SOURCE_DSN`（空则回退 `PG_DSN`）** 执行。

### 4.4 连接与驱动

| 项 | 约定 |
|----|------|
| Checkpointer | `psycopg` + langgraph-checkpoint-postgres（已有） |
| 知识（langchain_pg） | async 优先（asyncpg / langchain-postgres 官方路径） |
| 连接池 | 分用途配置上限；生产建议 PgBouncer（可选，文档说明） |
| 迁移 | **SQL 文件**放 `apps/api/migrations/`，幂等；由 `scripts/apply_migrations.py`（或等价）执行 |

#### 4.4.1 双驱动共存策略

同一 PG 实例下 checkpointer（`psycopg` 同步）与知识（`asyncpg`）共存：

| 项 | 策略 |
|----|------|
| DSN | 默认共用 `PG_DSN`；知识可单独 `KB_DSN` 覆盖 |
| 连接池上限 | **分池**：checkpointer ≤ 5、knowledge ≤ 10（可通过 env 覆盖） |
| 生命周期 | 均在 `lifespan.py` 创建 / 关闭；不跨用途借连接 |
| PgBouncer | 可选；若用，checkpointer 走 transaction 模式、knowledge 走 session 模式 |

### 4.5 单机拓扑（目标）

```text
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ apps/web    │────▶│ apps/api     │────▶│ PostgreSQL 16   │
│ AI 控制台   │     │ uvicorn      │     │ + pgvector      │
└─────────────┘     └──────┬───────┘     │ checkpointer    │
                           │             │ events / runs   │
                           │             │ knowledge.*     │
                           │             └─────────────────┘
                           │ 多机时
                           ▼
                    ┌──────────────┐
                    │ Redis 7      │
                    │ 锁 / 限流    │
                    └──────────────┘
         Embedding 服务（HTTP，OpenAI 兼容）──► api（知识后端）
```

一键体验：Fake 档无需 compose；完整 RAG 档用 `docker compose --profile rag up -d` 起 **pgvector**（+ 可选 Redis）；API 本地或 compose 内启动。

---

## 5. 知识后端

### 5.1 后端矩阵（能力地图）

| 能力 | `fake` | `langchain_pg` | `external` | `product` |
|------|:------:|:--------------:|:----------:|:---------:|
| 向量检索 | 模拟 | ✓ | ✓（下游） | ✓ |
| 混合检索 | — | ✓（可配） | 视下游 | ✓ |
| 入库 | 内存 | ✓ | 可选 | ✓ |
| 租户硬隔离 | ✓ | ✓ | ✓（协议强制） | ✓ |
| 落地阶段 | 已有 | **R-A（钉死先做）** | R-C | R-C+ |
| extra | 无 | `rag` / `rag-langchain` | 无重依赖 | `rag-product` |

### 5.2 配置

| 变量 | 默认 | 档 |
|------|------|-----|
| `KNOWLEDGE_BACKEND` | `fake` | B 启动项 |
| `KB_DSN` | 空→`PG_DSN` | B |
| `EMBED_*` | — | B/C（Key 为 C） |
| `KB_EXTERNAL_BASE_URL` | — | B |
| `KB_EXTERNAL_API_KEY` | — | C |

切换后端：**不改业务插件代码**；只改配置 + 安装对应 extra。

### 5.3 外部协议

见 [external-rag-protocol.md](./2026-07-27-external-rag-protocol.md)。  
不支持入库时：`KnowledgeIngest` 明确 `unsupported`，禁止假装成功。

### 5.4 分期验收

| 阶段 | 验收（说人话） |
|------|----------------|
| R-A | `langchain_pg` 可搜；租户 A 看不到 B；`demo_rag` citation 字段对齐 `KnowledgeHit`（`chunk_id`/`doc_id`/…） |
| R-B | `/ingest` 文本入库后可搜；**底座提供**入库任务 status HTTP API（控制台 UI 可晚到 C4） |
| R-C | Mock external 可接；可选 product；评测脚本可跑 |

---

## 6. 底座为控制台提供的 API

控制台自身 UI 见 [ai-admin-console-design.md](./2026-07-27-ai-admin-console-design.md)。  
**底座责任：** 提供稳定管理 API，不实现业务页面。  
> **管理 API 契约真源：** [管理后端最终形态 Spec §4](./2026-07-27-admin-backend-final-spec.md)。本节为摘要。

| API | 权限 | 阶段 | 用途 |
|-----|------|------|------|
| `GET /admin/overview` | `admin:read` | C0 | 总览聚合（backend 探测 + infra_ready + 24h Run/错误） |
| `GET /admin/domains`（扩展字段） | `admin:domains` | C0 | 插件清单；`required_permissions` = 该插件各 tool 权限**并集** |
| `GET /admin/config` | `admin:config` / read | C0 | 配置只读（分档） |
| `GET /ready` | 公开或只读 | 已有 | 依赖就绪 |
| `GET /admin/audit/export` | `admin:audit` | 已有 | 审计 |
| `GET /runs/*`、`/threads/*` | 业务/管理 | 已有 | 回放 |
| `GET /admin/tools` | `admin:tools` | C1 | 工具目录 + 矩阵 |
| `POST /admin/tools/{name}/invoke` | `admin:tools` | C1 | 试调（默认关） |
| `GET /admin/runs` | `admin:read` | C1 | Run 列表（分页/筛选） |
| `PUT /admin/config/{key}` | `admin:config` | C2+ | 热写（仅 tier A，有审计） |
| `/prompts/*` | `admin:prompts` | C2 | Prompt CRUD + publish |
| `GET /admin/usage/tokens` | `admin:usage` | C3 | 用量 |
| `GET /admin/knowledge/status` | `admin:knowledge` | C4 | 知识后端状态（provider 由 R-B+ 注入） |

**C0 硬约束：** tier B/C 不可热写；控制台 C0 不提供热写入口（C2 起档 A 可写）。

### 6.1 C0 前置改造（已完成）

1. **Run 投影扩展**：`run_lifecycle` / `project_turn` 已写 `route`、`started_at`、`ended_at`。  
2. **域 catalog 快照**：`lifespan.py` 构建 `app.state.domain_catalog`；`GET /admin/domains` 返回 `{domains:[...]}`。

---

## 7. 配置模型

### 7.1 三档

| 档 | 含义 | 控制台 | 存储 |
|----|------|--------|------|
| A 可热配 | 改完对后续 Run 生效 | C2+ 可写 | ConfigProvider（开发 `MemoryConfigProvider`；生产 DB/K-V 待接） |
| B 启动态 | 改了需重启 | **只读** | env / 部署 |
| C 密钥 | API Key、密码 | 仅「已配置」 | 密钥托管 / env；**不明文** |

### 7.2 ConfigProvider Port（声明）

- 底座 **包含** `ConfigProvider` Port（`get` / 可选 `set` + 审计）。  
- **C0：** 可不实现持久热配；`GET /admin/config` 可从 `Settings` 投影只读视图。  
- **C2 前：** 另写短设计（存储表、冲突、回滚）；未完成前禁止生产热写。

---

## 8. 安全与治理

| 能力 | 要求 |
|------|------|
| 工具 | list + invoke 双检；deny 不进 tool list |
| 数据 | DataFilter 白名单；无规则 → 空 |
| 租户 | 检索/入库/查库 Port 强制 `tenant_id` |
| 审批 | 释锁 + 同 run 续跑 |
| 审计 | append-only；导出去大字段 |
| 管理面 | §4.7；写操作必审计 |

开源仓库另备 `SECURITY.md`（漏洞上报），属发布卫生，不在本 Spec 展开。

---

## 9. 可观测与验证

### 9.1 运行面

- `/health`、`/ready`（未启用依赖标 skipped）、`/metrics`  
- EventLog 回放；失败先落库语义不变  

### 9.2 知识评测（发布门槛 · 目标值可在 R-C 微调）

| 项 | 最低要求 |
|----|----------|
| 样例集 | ≥ **20** 条中文金标 QA（可含合成） |
| 指标 | hit@3、延迟 p95 |
| 门禁 | 脚本失败 exit 1；CI 可选 job（需 PG+embedding） |
| 基线 | R-C 定稿时写入 `docs/knowledge-base.md`（例如 hit@3 ≥ 0.6 仅作初值） |

### 9.3 架构门禁

- import-linter + 扫描：domains / application 不依赖引擎包  
- 联合 pytest（core + api）主路径默认 **不** 要求 pgvector  

---

## 10. 开源可发布定义（v2.1）

### 10.1 版本含义

| 标签 | 含义 |
|------|------|
| v2.0 | M0–M10（当前主线已合入） |
| **v2.1** | + **M11**（至少 R-A+R-B）+ **M12 C0** |
| 其后 | R-C、控制台 C1+、行业重插件 |

### 10.2 发布前 Checklist

**功能**

- [ ] `KNOWLEDGE_BACKEND=langchain_pg` 真检索 + 跨租户隔离  
- [ ] `/ingest` 文本入库 → 检索闭环（R-B）  
- [ ] `demo_rag`（或等价）SSE 含合法 citation  
- [x] AI 控制台 C0–C4：`apps/web` 侧栏总览 / 调试 / 插件 / 配置 / Tools / Runs / Prompts / 用量 / 知识  
- [ ] 官方查数样板插件 `demo_datasource`：接真实 PG 数据源、走 DataSource Port  

**工程**

- [ ] `docker compose`：PG（**pgvector**）一键起；README 分两档 Quick Start（Fake 5min / 完整 RAG 30min）  
- [ ] CI 绿（pytest + architecture gates）  
- [ ] LICENSE 存在（仓库已有）；CONTRIBUTING / CHANGELOG 可用  
- [ ] `.env.example` 含知识相关变量注释  
- [ ] 安全：默认无 stub 生产配置；密钥不进仓库  

**文档**

- [ ] README 指向三类总纲 + 本 Spec + 收敛说明  
- [ ] deploy / knowledge-base / add-a-domain / contracts 与实现对齐  
- [ ] 外部 RAG 协议（若宣称支持 external）  

### 10.3 对外话术（禁止夸大）

> AgentBridge v2.1：可自托管的 Agent 接入底座；支持工具、查数、可换知识后端与 AI 控制台。  
> **不是** RAG_Agent 产品的完整业务功能复制件；行业场景请用业务插件扩展。

> **总话术以本节为准。** 管理后端 Spec / 业务插件 Spec 仅追加本轨一句，不另起对外主承诺。

---

## 11. 部署拓扑（摘要）

| 模式 | 进程 | 存储 |
|------|------|------|
| 开发 | api（+ web 可选） | 内存 |
| 单机 | api + web；可选独立 ingest-worker | PG+pgvector |
| 多机 | 多 api + Redis + 集中 PG | PG + Redis |

Embedding：**进程外 HTTP 服务**（TEI / 云 API）；不可用时 `/ready` 报告。

#### 11.1 Embedding 降级表

| `/ready` 中 embedding 状态 | `retrieve()` 行为 | `/ingest` 行为 |
|---|---|---|
| **healthy** | 正常检索 | 正常入库 |
| **degraded**（延迟高 / 部分模型不可用） | 正常检索，日志 warn | 正常入库，日志 warn |
| **unavailable** | 返回空结果 + 响应头 `X-Bridge-Degraded: embedding`；不 500 | 拒绝（HTTP 503，`code=embedding_unavailable`） |
| **unconfigured**（`KNOWLEDGE_BACKEND=fake`） | FakeRetriever 逻辑 | FakeIngest 逻辑 |

> 降级目标：对话主路径不因 embedding 挂掉而 500；知识质量下降可观测。

---

## 12. 插件契约（底座对 ③ 的要求）

业务插件 **必须**：

1. 仅通过 registry 注册 graph / tools / input_builder  
2. 检索只使用注入的 `Retriever` Port  
3. 扩展事件类型符合 `x.<plugin>.*`；citation 用 `x.bridge.citation`  
4. 声明 `required_permissions`；接受 list+invoke 双检  
5. 不持有 EventSink；不 import adapters / 引擎 SDK  

业务插件 **可以**：

- 自带长任务 worker（报告等），但组装入口独立、不污染 core  
- 依赖 **LLM Gateway**（`ctx.metadata["llm_gateway"]`）、DataSource、Approval 等已有 Port  

> **命名：** 产品/文档可称「Gateway」；运行时 metadata key 固定为 **`llm_gateway`**（见业务插件 Spec §4）。

详见 [业务插件最终形态 Spec](./2026-07-27-business-plugins-final-spec.md)、[add-a-domain.md](../../add-a-domain.md)。

---

## 13. 相关文档索引

| 文档 | 角色 |
|------|------|
| [design-tracks.md](../../design-tracks.md) | 三类总纲 |
| [scheme-convergence.md](./2026-07-27-scheme-convergence.md) | 近期拍板 |
| [rag-production-design.md](./2026-07-27-rag-production-design.md) | 多知识后端细节 |
| [external-rag-protocol.md](./2026-07-27-external-rag-protocol.md) | 外部 RAG 协议 |
| [ai-admin-console-design.md](./2026-07-27-ai-admin-console-design.md) | 控制台 |
| [business-plugins-final-spec.md](./2026-07-27-business-plugins-final-spec.md) | 业务插件最终形态 |
| [Plan6](../plans/2026-07-27-plan6-rag-production.md) / [Plan7](../plans/2026-07-27-plan7-ai-console-c0.md) | 实施任务 |
| [00-AgentBridge完整方案.md](../../00-AgentBridge完整方案.md) | 产品总约定 |
| [roadmap.md](../../roadmap.md) | 里程碑 |

---

## 14. 成功标准（底座最终形态）

集成方可以：

1. 按 Quick Start（Fake 档）5 分钟跑通对话；按完整 RAG 档 30 分钟跑通知识问答  
2. 打开 AI 控制台看到插件与配置只读、完成联调  
3. 切换 `langchain_pg` 后，知识问答带 citation，跨租户隔离  
4. 新增业务插件不改 core，只注册 domains  
5. 客户有外部 RAG 时，按协议接 `external`（R-C）  

到此视为：**底座达到开源可发布级（v2.1 目标态）**。
