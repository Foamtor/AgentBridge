# AgentBridge 管理后端最终形态 Spec（开源可发布级）

> **状态：** 设计定稿 v2.1（C0–C4 已在 `feat/admin-console-c0-c4` 落地；C4 知识 status 待底座 provider 注入）  
> **日期：** 2026-07-27（修订 2026-07-27）  
> **读者：** 平台管理员 · 集成开发者 · 开源贡献者  
> **归属：** 设计三类之 **② 管理后台**（见 [design-tracks.md](../../design-tracks.md)）  
> **关联：** [底座最终形态 Spec](./2026-07-27-platform-final-spec.md)、[方案收敛](./2026-07-27-scheme-convergence.md)、[Plan7 C0](../plans/2026-07-27-plan7-ai-console-c0.md)

---

## 0. 一句话

管理后端是 AgentBridge 的 **AI 控制面**：让管理员看清楚「接了哪些 AI 能力、是否健康、谁能用、用得怎样」，并在受控条件下做配置与治理。  
**它不是客户业务后台。**

---

## 1. 目标与边界

### 1.1 目标

| 目标 | 说明 |
|------|------|
| 调试联调 | 选插件发请求、看事件、处理审批、回放 run |
| 能力可见 | 插件、tools、模型、知识后端状态可见 |
| 配置治理 | 配置分档展示；热写分期开放 |
| 用量治理 | token/调用量统计（分期） |
| 安全合规 | admin 权限、写操作审计、密钥不明文 |

### 1.2 不做

| 不做 | 原因 |
|------|------|
| 客户业务前端页面 | 属 ③ 业务插件或客户系统 |
| 企业 IAM 替代 | 复用 OIDC/JWT，不造账号中心 |
| 控制台里实现业务算法 | 检索/报告逻辑属于底座或插件 |

---

## 2. 形态与分期

### 2.1 形态

- 前端载体：`apps/web`（升级，不新起 `apps/admin`）  
- 后端载体：`apps/api/routes/admin*.py` + 既有 `/runs` `/threads` `/approvals`  
- 以 API 驱动，UI 只是面板层

### 2.2 分期（M12）

| 期 | 范围 | 约束 |
|----|------|------|
| **C0** | 总览（含 24h Run/错误统计）、调试增强、插件列表、配置只读 | **禁止热写、禁止 Token** |
| C1 | Tools 目录 + 权限矩阵 + 可选试调 + **Run 列表页** | 试调默认关（`ADMIN_TOOL_INVOKE_ENABLED=false`） |
| C2 | Prompt 管理 + 档 A 热配 | 需 ConfigProvider + 写审计 |
| C3 | 模型与 Token 用量（`tenant` / `route` / `model`） | 需 Gateway 上报契约；无数据不造假 |
| C4 | 知识后端状态 + 入库任务面板 | **UI 在 ②**；status API **在 ① R-B+** |

**收敛硬规则：** v2.1 只要求 C0 可用。

### 2.3 决策纪要（2026-07-27 修订）

| 议题 | 决策 |
|------|------|
| 文档分工 | `admin-backend-final-spec` = API/权限/分期/验收真源；`ai-admin-console-design` = 前端 IA/线框（冲突以本 spec 为准） |
| C0 总览 | 展示近 24h **Run 总数**与**错误 Run 数**；**不展示 Token** |
| 配置热写 | **C2+** 开放 `PUT /admin/config/{key}`（与 Prompt 同期；须 ConfigProvider） |
| C1 Tools 试调 | `POST /admin/tools/{name}/invoke` 可选，环境开关默认关，`admin:tools` + 审计 |
| C1 运行回放 | 新增侧栏 `/runs` 列表页；详情仍用 `GET /runs/{id}`、`/events` |
| Run 列表 API | 新增 `GET /admin/runs`（管理列表）；**不**占用业务契约 `GET /runs` |
| C3 Token 粒度 | `tenant_id` + `route` + `model` 三维分组 |
| Plan7 T7 `demo_datasource` | **属 ③ 业务插件轨**，不在本 spec 范围 |
| 代码复核（v2.1） | C0 前置：Run 投影扩展（§6.2）、域元数据（§6.3）、配置 manifest（§5.3）；`domains` 响应由数组改为对象 |

---

## 3. 信息架构（目标态）

```text
AI 控制台
├── 总览
├── 调试
├── 业务插件
├── Tools
├── Prompts
├── 模型与用量
├── 知识后端
├── 运行与回放
├── 配置中心
└── 治理
```

**C0 最小集：** 总览 / 调试 / 业务插件 / 配置只读。

### 3.1 C0 页面线框（文字版）

**总览页**（数据来自 `GET /admin/overview`，线框详见 [console-design §5.1](./2026-07-27-ai-admin-console-design.md)）
- 卡片 1：插件数（已注册 / graph 就绪）
- 卡片 2：LLM Backend 类型 + **探测状态**（见 §4.1 overview 规则）
- 卡片 3：Knowledge Backend 类型 + **探测状态**（与 `/ready` 解耦）
- 卡片 4：**基础设施就绪**（透传 `GET /ready` 的 `checks`；词汇 `ready` / `not_ready`）
- 卡片 5：近 24h Run 总数、错误 Run 数（**不含 Token**；依赖 §6.2 Run 投影）
- 底部：最近 5 条失败 run（可选，有则展示）

**调试页**
- 域选择器 → 输入框 → SSE 事件面板（含 citation 高亮）
- 右侧：审批待处理列表（有 `awaiting_approval` 时显示按钮）
- 入口：点击 run_id 跳转回放

**业务插件页**
- 表格：name / description / tools 数 / 权限需求 / graph 状态

**配置只读页**
- 三列分组（A 可热配 / B 启动态 / C 密钥），每行：key / value（C 档显示 ●已配置 / ○未配置） / 描述

---

## 4. 管理 API 契约（后端责任）

> **契约真源：** 管理 API 以本节为准；业务 API（`/chat/*`、`/runs/*`）以 [contracts.md](../../contracts.md) 为准。两处重复路径以 contracts.md 优先。

| API | 阶段 | 权限 | 说明 |
|-----|------|------|------|
| `GET /admin/overview` | C0 | `admin:read` | 总览聚合（24h Run/错误、backend 探测、infra ready） |
| `GET /admin/domains` | C0 | `admin:domains` | 插件列表与摘要 |
| `GET /admin/config` | C0 | `admin:config` / `admin:read` | 配置只读分档 |
| `GET /admin/audit/export` | 已有 | `admin:audit` | 审计导出 |
| `GET /runs/{id}`、`/runs/{id}/events` | 已有 | 业务/管理 | 单 Run 回放 |
| `GET /threads/*` | 已有 | 业务/管理 | Thread 排障 |
| 调试页（`/chat/stream` 等） | C0 | `admin:debug` **或** 业务对话权限 | 见 §7.1 |
| `GET /admin/tools` | C1 | `admin:tools` / `admin:read` | 工具目录 + 权限矩阵 |
| `POST /admin/tools/{name}/invoke` | C1 | `admin:tools` | 可选试调；默认关，见 §4.3 |
| `GET /admin/runs` | C1 | `admin:read` | Run 列表（分页/筛选） |
| `/prompts/*` | C2 | `admin:prompts` | Prompt 管理（见 §5.2） |
| `PUT /admin/config/{key}` | C2+ | `admin:config` | 热配写入（仅 tier=A） |
| `GET /admin/usage/tokens` | C3 | `admin:usage` | 用量（`tenant`/`route`/`model`） |
| `GET /admin/knowledge/status` | C4 | `admin:knowledge` | **API 在 ① R-B+**；② 仅 UI |

### 4.1 C0 响应示例

#### `GET /admin/overview`

```json
{
  "domains": { "registered": 7, "graph_ready": 7 },
  "llm_backend": { "type": "gateway", "status": "ok" },
  "knowledge_backend": { "type": "langchain_pg", "status": "degraded", "message": "embed probe failed" },
  "infra_ready": {
    "status": "ready",
    "checks": {
      "checkpointer": { "status": "ok" },
      "event_log": { "status": "ok" },
      "data_source": { "status": "skipped", "reason": "ENABLE_DATA_SOURCE=false" }
    }
  },
  "runs_24h": { "total": 128, "errors": 5 },
  "recent_failed_runs": [
    {
      "run_id": "r-abc",
      "route": "demo_rag",
      "status": "error",
      "started_at": "2026-07-27T10:00:00Z"
    }
  ]
}
```

**字段规则**

| 块 | 来源 | 说明 |
|----|------|------|
| `domains` | `domain_catalog`（§6.3） | `registered` = 已注册 route 数；`graph_ready` = 有 graph 的 route 数 |
| `llm_backend.type` | `settings.llm_backend` | `direct` / `gateway` |
| `llm_backend.status` | 管理端探测 | `ok` / `degraded` / `skipped`；**不**复用 `/ready` 词汇 |
| `knowledge_backend.type` | `settings.knowledge_backend` | `fake` / `langchain_pg` |
| `knowledge_backend.status` | 管理端探测 | `fake` → `skipped`；`langchain_pg` → 轻量 probe（如 retriever 可达性），失败 → `degraded` |
| `infra_ready` | 内部调用与 `GET /ready` 相同逻辑 | 字段名刻意与 backend 探测区分；`status` 为 `ready` / `not_ready` |
| `runs_24h` | `RunStore` + §6.2 时间字段 | 按 JWT `tenant_id`、近 24h 窗统计；**不含 Token** |
| `recent_failed_runs` | 同上 | `status in (error, cancelled)`，最多 5 条，按 `started_at` 倒序 |

无 Run 数据时：`runs_24h` 为 `{ "total": 0, "errors": 0 }`，`recent_failed_runs` 为 `[]`。

#### `GET /admin/config`

C0 从 `Settings` + **§5.3 manifest** 投影；档 A 在 C0 可为空列表。

```json
{
  "items": [
    { "key": "LLM_BACKEND",       "value": "gateway",  "tier": "B", "description": "模型路由方式" },
    { "key": "KNOWLEDGE_BACKEND", "value": "fake",     "tier": "B", "description": "知识后端类型" },
    { "key": "AUTH_REQUIRED",     "value": false,      "tier": "B", "description": "是否强制鉴权" },
    { "key": "EMBED_MODEL",       "value": "text-embedding-3-small", "tier": "B", "description": "Embedding 模型名" },
    { "key": "EMBED_API_KEY",     "value": null,       "tier": "C", "configured": true, "description": "Embedding API Key" },
    { "key": "LLM_API_KEY",       "value": null,       "tier": "C", "configured": false, "description": "LLM API Key" },
    { "key": "OIDC_JWT_SECRET",   "value": null,       "tier": "C", "configured": true, "description": "JWT 验签密钥" }
  ]
}
```

规则：`tier=C` 项 `value` 始终为 `null`，用 `configured` 表示是否已配；`tier=A` 项 **C0 不返回**（或返回空）；C2+ 可写项随 ConfigProvider 扩展 manifest。

#### `GET /admin/domains`

**迁移说明（相对当前代码）：** 现有实现返回 JSON **数组** `[{"name","kind"}]`；C0 目标为 **对象** `{ "domains": [...] }`（破坏性变更，仅测试依赖，以对齐本契约）。

```json
{
  "domains": [
    {
      "name": "demo_rag",
      "description": "RAG 知识问答示例",
      "tools": ["search_knowledge"],
      "required_permissions": ["knowledge:read"],
      "graph_registered": true
    },
    {
      "name": "demo_tools",
      "description": "工具联动示例",
      "tools": ["add", "delete_records"],
      "required_permissions": [],
      "graph_registered": true
    }
  ]
}
```

**字段来源（§6.3）**

| 字段 | 规则 |
|------|------|
| `name` | `ToolRegistry` / `GraphRegistry` 的 route 键 |
| `description` | 各域 `bootstrap.DOMAIN_META["description"]` |
| `tools[]` | 该 route 下各 tool 的 `tool.name` |
| `required_permissions` | 各 tool `attach_tool_meta(... required_permissions)` 的**并集**（去重排序）；`required_roles` **不计入**此字段 |
| `graph_registered` | 同名 route 在 `GraphRegistry` 已注册 |

插件 bootstrap 不必单独声明插件级权限列表。

### 4.2 C0 禁止项（API）

- 不提供 `PUT /admin/config/*`（或后端返回 404/501）
- 不提供 token 用量 API（`GET /admin/usage/tokens`）
- 不提供业务数据管理 API

### 4.3 C1 响应示例

#### `GET /admin/tools`

```json
{
  "tools": [
    {
      "name": "search_knowledge",
      "domain": "demo_rag",
      "description": "检索知识库",
      "required_permissions": ["knowledge:read"],
      "required_roles": [],
      "invoke_allowed": false
    }
  ],
  "matrix": {
    "roles": ["admin", "viewer"],
    "tools": {
      "search_knowledge": { "admin": "allow", "viewer": "deny" }
    }
  }
}
```

**权限矩阵规则**

- `matrix.roles` 来自环境变量 `POLICY_MATRIX_ROLES`（逗号分隔，默认 `admin,viewer`）；**不是** JWT 运行时枚举
- 对每个 `(role, tool)`：用 `RunContext(roles=[role])` 调用 `RolePolicyEngine.filter_tools(route, tools, ctx)`；在结果中 → `allow`，否则 → `deny`
- `required_roles` 类 tool（如 `delete_records`）同样参与矩阵，但**不**进入 `required_permissions` 并集
- `matrix` 为只读投影，非写接口

#### `POST /admin/tools/{name}/invoke`

环境开关 `ADMIN_TOOL_INVOKE_ENABLED`（默认 `false`）。关 → **403** `tool_invoke_disabled`。

请求：

```json
{ "arguments": { "query": "test" }, "tenant_id": "acme" }
```

响应：`{ "ok": true, "result": { ... } }` 或结构化错误。必须写审计 `action=admin.tool_invoke`。

#### `GET /admin/runs`

查询：`status`、`route`、`since`、`until`、`limit`（默认 20，最大 100）、`cursor`。

```json
{
  "items": [
    {
      "run_id": "r-abc",
      "thread_id": "t-1",
      "route": "demo_rag",
      "status": "done",
      "tenant_id": "acme",
      "started_at": "2026-07-27T10:00:00Z",
      "ended_at": "2026-07-27T10:00:05Z"
    }
  ],
  "next_cursor": null
}
```

`status` 枚举与 RunStore 一致：`done` | `error` | `awaiting_approval` | `cancelled` | `pending`（进行中，若有）。

实现基于 `RunStore.list_by_tenant` + §6.2 字段过滤分页；单 Run 详情与事件仍用 `GET /runs/{id}`、`GET /runs/{id}/events`。

### 4.4 C2 响应示例

**前置：** 底座 `ConfigProvider` Port（`get` / `set` + 审计）已落地。

#### `PUT /admin/config/{key}`

仅 **tier=A**；tier B/C → **400** `config_not_writable`。

```json
{ "value": 60 }
```

响应：`{ "key": "RATE_LIMIT_PER_MINUTE", "value": 60, "tier": "A" }`（示例；实际档 A 键以 ConfigProvider manifest 为准）。写操作必审计。

#### `/prompts/*`（管理轨新增）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/prompts` | `admin:prompts` / read | 列表 |
| GET | `/prompts/{name}` | 同上 | 内容与元数据 |
| PUT | `/prompts/{name}` | `admin:prompts` | 创建/更新 + 审计 |
| POST | `/prompts/{name}/publish` | `admin:prompts` | 版本发布（C2 末可选） |

Prompt 优先级见 §5.2。

### 4.5 C3 响应示例

**前置：** LLM Gateway 上报契约（`tenant_id`、`route`、`model`、token 计数、时间戳）。

#### `GET /admin/usage/tokens`

查询：`since`、`until`、`group_by=tenant|route|model`。

```json
{
  "window": { "since": "2026-07-26T00:00:00Z", "until": "2026-07-27T00:00:00Z" },
  "group_by": "route",
  "items": [
    {
      "tenant_id": "acme",
      "route": "demo_rag",
      "model": "gpt-4o",
      "input_tokens": 1200,
      "output_tokens": 340
    }
  ],
  "totals": { "input_tokens": 1200, "output_tokens": 340 }
}
```

无上报数据 → **200** + `items: []`；**禁止**伪造或估算 Token。

### 4.6 C4 响应示例

**API 真源在 ① 底座**（R-B+）：`GET /admin/knowledge/status`。管理轨 C4 仅消费并展示。

```json
{
  "backend": "langchain_pg",
  "healthy": true,
  "embedding": { "status": "ok", "model": "text-embedding-3-small" },
  "ingest_jobs": [
    { "job_id": "j-1", "status": "completed", "updated_at": "2026-07-27T09:00:00Z" }
  ]
}
```

`ingest_jobs` 仅当底座启用 `/ingest` 流水线时有数据。C4 **不做**入库写操作。

---

## 5. 配置中心模型（分档）

| 档 | 含义 | 控制台策略 | 存储 |
|----|------|------------|------|
| A 可热配 | 改完影响后续 run | C2+ 才可写 | ConfigProvider（DB/KV） |
| B 启动态 | 改完需重启 | 只读展示 | env / 部署 |
| C 密钥 | key/password | 仅状态，不明文 | 密钥托管 / env |

### 5.1 安全要求

1. 密钥只显示 `configured: true/false`  
2. 写配置必须审计（操作者、旧值摘要、新值摘要、时间）  
3. 高风险键需二次确认（C2+）

### 5.2 Prompt 真源时间线

| 阶段 | 真源 | 控制台 |
|------|------|--------|
| **C2 前（含 v2.1）** | 各插件目录 `prompts/` 文件（插件自行加载） | **无** Prompt CRUD |
| **C2+** | 平台 Prompt 存储（经 `/prompts/*` + ConfigProvider 审计） | Prompts 页可读写 |

**冲突规则（C2+）：** 若平台为某 `route` 配置了覆盖项，**平台配置优先**于插件目录文件；未配置则回退插件文件。禁止两套同时「静默生效」却无优先级说明。

### 5.3 C0 配置 manifest（`Settings` 投影）

`GET /admin/config` **不得**硬编码虚构键；C0 至少包含下表（env 名 → `apps/api/config/settings.py` 字段）：

| tier | key（响应用大写 env 名） | settings 字段 | 说明 |
|------|-------------------------|---------------|------|
| B | `LLM_BACKEND` | `llm_backend` | 模型路由 |
| B | `KNOWLEDGE_BACKEND` | `knowledge_backend` | 知识后端 |
| B | `AUTH_REQUIRED` | `auth_required` | 鉴权开关 |
| B | `LOCK_BACKEND` | `lock_backend` | 线程锁后端 |
| B | `RATE_LIMIT_BACKEND` | `rate_limit_backend` | 限流后端 |
| B | `USE_MEMORY_CHECKPOINTER` | `use_memory_checkpointer` | 内存 checkpoint |
| B | `ENABLE_DATA_SOURCE` | `enable_data_source` | 查数 Port 开关 |
| B | `HOOKS_BACKEND` | `hooks_backend` | Hooks 实现 |
| B | `EMBED_MODEL` | `embed_model` | Embedding 模型 |
| B | `EMBED_API_BASE` | `embed_api_base` | Embedding HTTP 基址 |
| B | `EMBED_DIMENSIONS` | `embed_dimensions` | 向量维度 |
| B | `POLICY_BUNDLE_VERSION` | `policy_bundle_version` | 策略包版本 |
| C | `EMBED_API_KEY` | `embed_api_key` | Embedding 密钥 |
| C | `LLM_API_KEY` | `llm_api_key` | LLM 密钥 |
| C | `OIDC_JWT_SECRET` | `oidc_jwt_secret` | JWT 验签 |
| C | `PG_PASSWORD` | `pg_password` | 数据库密码 |
| C | `DATA_SOURCE_DSN` | `data_source_dsn` | 查数 DSN |
| C | `KB_DSN` | `kb_dsn` | 知识库 DSN |

**档 A（C0）：** manifest 返回 **空** 或省略 tier A 分组；C2+ 随 ConfigProvider 扩展（如 `RATE_LIMIT_PER_MINUTE` 等热配项）。

实现建议：`apps/api/routes/admin_config.py` 内维护 `_CONFIG_MANIFEST: list[ConfigItemSpec]`，单测断言与 `Settings` 字段同步。

---

## 6. 数据与存储（管理后端）

管理后端本身不引入新数据库类型，复用底座：

- PostgreSQL：审计记录、回放、（未来）配置持久化、（未来）用量聚合  
- Redis：仅多机运行时辅助，不作为配置真源

### 6.1 最低数据库前提

- 与底座一致：PG ≥ 16  
- C0 不要求新增表（可从现有 settings + audit + runs 投影）  
- C0 默认 `MemoryRunStore`（进程内）；重启丢 Run 列表——开发可接受；生产持久化 RunStore 为 C1+ 可选增强

### 6.2 Run 投影扩展（C0 前置，① 底座）

**现状：** `RunStore.upsert` 仅写 `run_id`、`tenant_id`、`thread_id`、`status`；**无** `route` / 时间戳，无法支撑 24h 统计与 `GET /admin/runs` 筛选。

**C0 实施前必须在 `run_lifecycle` / `project_turn` 补齐：**

| 字段 | 写入时机 | 格式 |
|------|----------|------|
| `route` | run 开始时 | 与 `/chat/stream` 的 `route` 一致 |
| `started_at` | run 开始时 | ISO-8601 UTC |
| `ended_at` | 终端状态（`done` / `error` / `cancelled`） | ISO-8601 UTC |
| `status` | 已有；枚举见 §4.3 | `done` \| `error` \| `awaiting_approval` \| … |

`awaiting_approval` 暂停时也应保留 `route` + `started_at`（已有 upsert 路径需扩展字段）。

**验收：** 跑一次 `/chat/stream` 后，`GET /runs/{id}` JSON 含 `route` 与 `started_at`；overview 24h 窗统计非恒 0（有 run 时）。

### 6.3 域元数据与 catalog（C0 前置，② 组装）

**现状：** `GET /admin/domains` 读 `tools.keys()`；无 `description`；`GraphRegistry` 未暴露给 route。

**约定：**

1. 每个 `apps/api/domains/*/bootstrap.py` 导出 `DOMAIN_META = {"description": "..."}`  
2. `lifespan.py` 在 `register_all` 后构建 **`domain_catalog`**（只读快照），挂 `app.state.domain_catalog`：

```python
# 形状示意
[
  {
    "name": "demo_rag",
    "description": "...",
    "tools": ["search_knowledge"],
    "required_permissions": ["knowledge:read"],
    "graph_registered": True,
  },
  ...
]
```

3. **禁止** route 直接持有可变 `GraphRegistry` 引用；catalog 在启动时一次性投影  
4. `GET /admin/domains` 返回 `{ "domains": app.state.domain_catalog }`

---

## 7. 权限与合规

建议权限集合：

- `admin:read`
- `admin:domains`
- `admin:debug`
- `admin:audit`
- `admin:config`
- `admin:tools`
- `admin:prompts`
- `admin:usage`
- `admin:knowledge`

规则：

1. 默认最小权限  
2. 所有写操作必审计  
3. 管理接口与业务接口可分 audience（部署策略）

### 7.1 `admin:debug` 映射

| 能力 | 权限 | 说明 |
|------|------|------|
| 打开控制台「调试」页 | `admin:debug` **或** `admin:read` | 页级守卫 |
| 发起 `/chat/stream` 联调 | 业务侧对话权限（与生产一致）+ 可选要求 `admin:debug` | 部署可选：仅 admin audience 可从控制台发流 |
| 审批决定 | `approval:decide`（已有） | 与调试页审批按钮共用 |

> `admin:debug` **不是**独立 HTTP 资源；它绑定控制台调试面。无此权限时隐藏调试入口，而非另造 `/admin/debug` API。

---

## 8. 可观测与验证

### 8.1 C0 验收

- [x] §6.2 Run 投影字段已落地（`route`、`started_at` 等）  
- [x] §6.3 各域 `DOMAIN_META` + `domain_catalog` 已落地  
- [x] `GET /admin/domains` 返回 `{ "domains": [...] }`（非裸数组）  
- [x] `GET /admin/overview`：backend 探测与 `infra_ready` 分离；24h 统计有效  
- [x] `GET /admin/config` 按 §5.3 manifest 投影；档 A 在 C0 为空；密钥不明文  
- [x] 控制台可看到插件、infra ready、配置只读  
- [x] 总览展示近 24h Run 总数与错误数（**无 Token 字段**）  
- [x] 调试页可发起请求并看到 SSE 事件  
- [x] 可跳转查看 run/threads 回放  
- [x] 无 `admin:*` 不可访问管理页关键 API  
- [x] 不出现业务前端信息架构  
- [x] C0 不提供 tier B/C 热写（`PUT` 仅 tier A，见 C2）

### 8.3 C1 验收

- [x] `GET /admin/tools` 返回完整工具目录与权限矩阵
- [x] `POST /admin/tools/{name}/invoke` 默认 403；开启开关后可试调且落审计
- [x] `GET /admin/runs` 列表可分页筛选；可进入 `GET /runs/{id}/events` 回放
- [x] 侧栏 `/runs`、`/tools` 页可加载

### 8.4 C2 验收

- [x] `ConfigProvider` 落地后，档 A 可 `PUT /admin/config/{key}` 且写审计（开发默认 `MemoryConfigProvider`）
- [x] tier B/C 热写返回 400
- [x] `/prompts/*` CRUD 可用；平台覆盖优先于插件文件（§5.2）
- [x] 配置只读页对档 A 显示「可编辑」标识

### 8.5 C3 验收

- [x] `GET /admin/usage/tokens` 支持 `tenant` / `route` / `model` 分组
- [x] 无 Gateway 数据时 UI 显示「暂无用量数据」，不展示假图表

### 8.6 C4 验收

- [x] 知识面板消费 `GET /admin/knowledge/status` 路由
- [x] 无 `knowledge_status_provider` 时返回 `503` + `blocked_by_base_r_b_status_api`；UI 显示阻塞提示
- [ ] 展示 backend 类型、健康探测、入库任务列表（依赖底座 R-B provider 注入）
- [x] 控制台不提供入库写入口

### 8.7 状态枚举统一（实现必须对齐）

| 字段 | 允许值 | 说明 |
|------|--------|------|
| `infra_ready.status` | `ready` \| `not_ready` | 仅用于基础设施就绪（对齐 `/ready` 语义） |
| `llm_backend.status` | `ok` \| `degraded` \| `skipped` \| `fail` | 管理端独立探测；不复用 `/ready` 词汇 |
| `knowledge_backend.status` | `ok` \| `degraded` \| `skipped` \| `fail` | `fake` 常见为 `skipped`；`langchain_pg` 可探测失败为 `degraded` |
| `runs[].status` | `pending` \| `awaiting_approval` \| `done` \| `error` \| `cancelled` | 来自 RunStore 投影；前后端渲染与筛选用这一组 |

### 8.2 性能与稳定（最低）

- 管理 API p95 < 300ms（不含大文件导出）  
- 审计导出支持流式，避免一次性内存爆炸

---

## 9. 开源可发布定义（管理后端）

### 9.1 v2.1 对管理后端的要求

- C0 可用（只读+调试）  
- 文档清楚说明 C1–C4 仍为后续  
- README / roadmap / architecture 与控制台定位一致

> 对外主话术见 [底座 Spec §10.3](./2026-07-27-platform-final-spec.md)。本轨追加：v2.1 控制台 = **C0 只读 + 调试**，不含热配与 Token 账单。

### 9.2 发布前 Checklist

- [ ] `apps/web` 文案统一为「AI 控制台」  
- [ ] `GET /admin/config` 已落地且密钥不明文  
- [ ] 管理 API 权限测试通过（含 `admin:debug` 页守卫）  
- [ ] 审计导出可用  
- [ ] 文档包含 C0 边界（无热写）

---

## 10. 与底座/插件的边界

| 事项 | 归属 |
|------|------|
| 检索引擎实现、入库流水线、status API | ① 底座 |
| 行业问答、分析报告、地图能力 | ③ 业务插件 |
| 官方样板插件（如 `demo_datasource`） | ③ 业务插件（**非** Plan7 管理轨范围） |
| 插件列表、配置可见、调试排障、Run/Tools 管理 UI | ② 管理后端 |

---

## 11. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 管理后台被当业务后台扩建 | 用边界清单卡住；超范围单独立项 |
| 热配导致线上误改 | C0 禁热写；C2+ 才启用并强制审计 |
| token 数据不准 | 未完成 LLM Gateway 上报契约前不展示账单结论 |
| 多实例配置漂移 | ConfigProvider 实现前只读，避免伪热配 |
| Prompt 双真源 | 见 §5.2 时间线与冲突规则 |
| Run 投影缺失导致 overview/runs 不可用 | §6.2 列为 C0 前置；Plan7 T0 先落地 |
| MemoryRunStore 重启丢历史 | 文档说明；生产 PG RunStore 后续增强 |
| domains 响应破坏性变更 | 仅内部测试依赖旧数组形态；C0 一次性切换 |

---

## 12. 相关文档

- [AI 控制台设计稿](./2026-07-27-ai-admin-console-design.md)
- [Plan7 C0](../plans/2026-07-27-plan7-ai-console-c0.md)
- [底座最终形态 Spec](./2026-07-27-platform-final-spec.md)
- [业务插件最终形态 Spec](./2026-07-27-business-plugins-final-spec.md)
- [方案收敛](./2026-07-27-scheme-convergence.md)
- [设计三类总纲](../../design-tracks.md)
