# AgentBridge 管理后端最终形态 Spec（开源可发布级）

> **状态：** 设计定稿 v2（C0–C4 分期对齐，待实现对齐）  
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
- 卡片 2：LLM Backend 类型 + 状态
- 卡片 3：Knowledge Backend 类型 + 状态
- 卡片 4：`/ready` 摘要（各依赖 healthy / degraded / skipped）
- 卡片 5：近 24h Run 总数、错误 Run 数（**不含 Token**）
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
| `GET /admin/overview` | C0 | `admin:read` | 总览聚合（24h Run/错误、ready 摘要） |
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
  "domains": { "registered": 4, "graph_ready": 4 },
  "llm_backend": { "type": "gateway", "status": "healthy" },
  "knowledge_backend": { "type": "langchain_pg", "status": "degraded" },
  "ready": {
    "status": "degraded",
    "checks": [
      { "name": "postgres", "status": "healthy" },
      { "name": "embedding", "status": "degraded", "message": "optional" }
    ]
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

规则：按 JWT `tenant_id` 统计近 24h；`runs_24h` **不含 Token**；无数据时计数为 `0`，`recent_failed_runs` 可为 `[]`。

#### `GET /admin/config`

```json
{
  "items": [
    { "key": "LLM_BACKEND",       "value": "gateway",  "tier": "B", "description": "模型路由方式" },
    { "key": "KNOWLEDGE_BACKEND", "value": "fake",     "tier": "B", "description": "知识后端类型" },
    { "key": "EMBED_MODEL",       "value": "text-embedding-3-small", "tier": "B", "description": "Embedding 模型" },
    { "key": "EMBED_API_KEY",     "value": null,       "tier": "C", "configured": true, "description": "Embedding API Key" },
    { "key": "MAX_TOOL_RETRIES",  "value": 3,          "tier": "A", "description": "工具重试上限" }
  ]
}
```

规则：`tier=C` 项 `value` 始终为 `null`，用 `configured` 表示是否已配；`tier=A` 项 C2+ 可写。

#### `GET /admin/domains`

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
      "tools": ["get_weather", "web_search"],
      "required_permissions": [],
      "graph_registered": true
    }
  ]
}
```

**聚合规则：** `required_permissions` = 该插件已注册各 tool 上 `attach_tool_meta(... required_permissions)` 的**并集**（去重排序）。插件 bootstrap 不必再单独声明一份插件级权限列表。

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

`matrix` 为当前 `role_policy` 包的**只读投影**，非写接口。

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
      "status": "completed",
      "tenant_id": "acme",
      "started_at": "2026-07-27T10:00:00Z",
      "ended_at": "2026-07-27T10:00:05Z"
    }
  ],
  "next_cursor": null
}
```

实现基于 `RunStore.list_by_tenant` + 过滤分页；单 Run 详情与事件仍用 `GET /runs/{id}`、`GET /runs/{id}/events`。

### 4.4 C2 响应示例

**前置：** 底座 `ConfigProvider` Port（`get` / `set` + 审计）已落地。

#### `PUT /admin/config/{key}`

仅 **tier=A**；tier B/C → **400** `config_not_writable`。

```json
{ "value": 5 }
```

响应：`{ "key": "MAX_TOOL_RETRIES", "value": 5, "tier": "A" }`。写操作必审计。

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

---

## 6. 数据与存储（管理后端）

管理后端本身不引入新数据库类型，复用底座：

- PostgreSQL：审计记录、回放、（未来）配置持久化、（未来）用量聚合  
- Redis：仅多机运行时辅助，不作为配置真源

### 6.1 最低数据库前提

- 与底座一致：PG ≥ 16  
- C0 不要求新增表（可从现有 settings + audit + runs 投影）

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

- [ ] 控制台可看到插件、ready 状态、配置只读  
- [ ] 总览展示近 24h Run 总数与错误数（**无 Token 字段**）
- [ ] 调试页可发起请求并看到 SSE 事件  
- [ ] 可跳转查看 run/threads 回放  
- [ ] 无 `admin:*` 不可访问管理页关键 API  
- [ ] 不出现业务前端信息架构
- [ ] `PUT /admin/config/*` 不可用（404/501）

### 8.3 C1 验收

- [ ] `GET /admin/tools` 返回完整工具目录与权限矩阵
- [ ] `POST /admin/tools/{name}/invoke` 默认 403；开启开关后可试调且落审计
- [ ] `GET /admin/runs` 列表可分页筛选；可进入 `GET /runs/{id}/events` 回放
- [ ] 侧栏 `/runs`、`/tools` 页可加载

### 8.4 C2 验收

- [ ] `ConfigProvider` 落地后，档 A 可 `PUT /admin/config/{key}` 且写审计
- [ ] tier B/C 热写返回 400
- [ ] `/prompts/*` CRUD 可用；平台覆盖优先于插件文件（§5.2）
- [ ] 配置只读页对档 A 显示「可编辑」标识

### 8.5 C3 验收

- [ ] `GET /admin/usage/tokens` 支持 `tenant` / `route` / `model` 分组
- [ ] 无 Gateway 数据时 UI 显示「暂无用量数据」，不展示假图表

### 8.6 C4 验收

- [ ] 知识面板消费底座 `GET /admin/knowledge/status`
- [ ] 展示 backend 类型、健康探测、入库任务列表（有则显示）
- [ ] 控制台不提供入库写入口

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

---

## 12. 相关文档

- [AI 控制台设计稿](./2026-07-27-ai-admin-console-design.md)
- [Plan7 C0](../plans/2026-07-27-plan7-ai-console-c0.md)
- [底座最终形态 Spec](./2026-07-27-platform-final-spec.md)
- [业务插件最终形态 Spec](./2026-07-27-business-plugins-final-spec.md)
- [方案收敛](./2026-07-27-scheme-convergence.md)
- [设计三类总纲](../../design-tracks.md)
