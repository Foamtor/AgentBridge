# AI 控制台（管理后台）— 架构设计

> **状态：** 设计稿 v2（与 [管理后端 final-spec](./2026-07-27-admin-backend-final-spec.md) 对齐）  
> **日期：** 2026-07-27（修订 2026-07-27）  
> **归属：** 设计三类之 **② 管理后台**（见 [design-tracks.md](../../design-tracks.md)）  
> **前端策略：** **C0 起升级现有 `apps/web`**，不另起 `apps/admin`（膨胀后再拆）  
> **不做：** 客户业务前端（一张图、行业工作台等）

---

## 1. 定位

> 给集成方 / 平台管理员用的 **框架 AI 控制台**：调试、配置、Tools、Prompt、Token/用量与治理。  
> 目标是让用户 **全面掌握已接到 AgentBridge 上的 AI 能力**。

**不是：** 业务系统后台、企业 IAM、云 Studio 拖拽造 Agent。

---

## 2. 用户与权限

| 角色 | 典型动作 | 权限（示意） |
|------|----------|--------------|
| 集成开发 | 选插件发对话、看 SSE、处理审批试跑 | 业务权限 + 调试；或 `admin:debug` |
| 平台管理员 | 改可热配项、管 Prompt、看用量、导出审计 | `admin:*` 细分（见下） |
| 只读运维 | 看 ready、配置只读、指标 | `admin:read` |

管理 API 继续对齐完整方案 §4.7；控制台所有写操作打审计。

建议权限码（可增量）：

| 权限 | 用途 |
|------|------|
| `admin:read` | 总览、配置只读、Run 列表（C0/C1） |
| `admin:domains` | 插件列表（已有） |
| `admin:audit` | 审计导出（已有） |
| `admin:debug` | 控制台调试发跑（可选，或复用业务权限） |
| `admin:tools` | Tools 目录与试调 |
| `admin:prompts` | Prompt 读写/发布 |
| `admin:config` | 可热配配置读写 |
| `admin:usage` | Token/调用量查看 |
| `admin:knowledge` | 知识后端状态 / 入库任务查看 |

---

## 3. 信息架构（目标态侧栏）

```text
AI 控制台（apps/web）
├── 总览         已接入能力、就绪、近 24h Run/错误（无 Token）
├── 调试         发对话 / 事件流 / 取消 / 审批（现有 Debug 升级）
├── 业务插件     route 列表、元数据、tools、graph 状态
├── Tools        工具目录、权限矩阵、可选试调（C1+，默认关）
├── 运行与回放   Run 列表 / 事件回放（C1 侧栏页）
├── Prompts      列表 / 版本 / 发布 / 回滚（C2+）
├── 模型与用量   Gateway 别名、Token 统计（C3+）
├── 知识后端     backend 类型、探测、入库任务（C4+）
├── 配置中心     只读（C0）→ 档 A 可写（C2+）
└── 治理         审计、策略包版本、限流/多机只读说明
```

**C0 最小集：** 总览 / 调试 / 业务插件 / 配置只读。  
**C1 新增侧栏：** 运行与回放 `/runs`、Tools `/tools`。

> **收敛约束（强制）：** C0 **禁止**配置热写、禁止 Token 账单、禁止当成业务后台。见 [方案收敛](./2026-07-27-scheme-convergence.md)。
---

## 4. 配置中心（原配置文件进管理端）

### 4.1 三档配置

| 档 | 含义 | 管理端 | 存储 |
|----|------|--------|------|
| **A. 可热配** | 改完可对后续 Run 生效 | 可读写 | DB / ConfigProvider（需落地） |
| **B. 启动态** | 改了需重启或滚动 | **只读展示** + 变更说明 | env / 部署清单 |
| **C. 密钥** | 密码、API Key | 仅「已配置/未配置」、轮换入口 | 密钥托管 / env；**不明文回显** |

### 4.2 档 A 示例（优先进控制台）

- 默认模型别名、各 route 默认 model  
- Prompt 绑定（route → prompt 名/版本）  
- 检索默认 `top_k`、是否 hybrid、默认检索档位  
- 功能开关：某官方示例插件是否对租户可见（若支持）  
- 单机限流阈值（若运行时支持热更）  

### 4.3 档 B 示例（只读）

- `LLM_BACKEND`、`KNOWLEDGE_BACKEND`、`MEMORY_BACKEND`  
- Checkpointer / Redis / 多机开关  
- `AUTH_REQUIRED`  

### 4.4 档 C 示例（永不进前端明文）

- `EMBED_API_KEY`、LLM API Key、`PG` 密码、JWT 密钥  

### 4.5 底座要求

- 引入或落实 **ConfigProvider Port**（完整方案已列）：`get(key)` / `set`（仅 admin）/ 变更审计。  
- 启动时：env 为底；热配覆盖非密钥项。  
- 本地无控制台时：仍可用 env/文件启动（开发不阻塞）。

---

## 5. 模块说明

### 5.1 总览（C0）

数据来自 `GET /admin/overview`（契约见 [管理 Spec §4.1](./2026-07-27-admin-backend-final-spec.md)）。

- 4 卡片：插件数、LLM backend、Knowledge backend、`/ready` 摘要
- 近 24h：**Run 总数**、**错误 Run 数**（**不展示 Token**）
- 底部：最近失败 run 列表（最多 5 条，可点进回放）

### 5.2 调试（C0 核心）

在现有 `DebugPage` 上增强：

| 能力 | 说明 |
|------|------|
| 选 route / 租户 / 模型 | 已有基础上补齐 |
| SSE 时间线 | 已有；高亮 citation / 审批事件 |
| 取消、409 提示 | 补强 |
| 审批操作 | 对接 `/approvals/*` |
| 一键打开本次 Run 回放 | 调 `/runs/{id}/events` |

### 5.3 业务插件

- 扩展 `GET /admin/domains`：名称、权限要求、tools 列表摘要、健康  
- 不提供业务侧配置页；插件若需深链，仅显示可选 URL（插件自声明）

### 5.4 Tools（C1）

- 只读目录：name、domain、`required_permissions`、描述  
- 权限矩阵：角色 × 工具可见/可调（只读可视化，来自 `GET /admin/tools` 的 `matrix`）  
- 试调：`POST /admin/tools/{name}/invoke`；`ADMIN_TOOL_INVOKE_ENABLED` 默认关；需 `admin:tools` + 审计

**线框：** 表格 + 矩阵热力图；选中 tool 显示「试调」按钮（仅开关开启时可用）。

### 5.5 Prompts（C2+）

- 对齐 PromptRegistry：列表、版本、变量说明、发布/回滚  
- 写操作：`admin:prompts` + 审计

### 5.6 模型与用量（C3）

两层概念，UI 分开：

1. **LLM Token 用量：** 按 `tenant` / `route` / `model` 聚合；依赖 Gateway 上报  
2. **接入凭证：** 服务账号状态；不替代客户 OIDC  

无数据时显示「暂无用量数据」，不展示假图表。

### 5.7 知识后端（C4）

- 消费底座 `GET /admin/knowledge/status`：backend 类型、探测结果  
- 入库任务列表只读（底座启用 `/ingest` 时有数据）

### 5.8 运行与回放（C1）

- 侧栏 `/runs`：`GET /admin/runs` 列表，支持 status/route/时间筛选与分页  
- 点击行：进入事件流视图（`GET /runs/{id}/events`）  
- C0 调试页保留 run_id 一键跳转，与 C1 列表页互通

### 5.9 治理

- 复用 `/admin/audit/export`、策略包版本只读展示  
- Thread 排障仍用 `/threads/*`（无独立侧栏页，C1+ 可选）

---

## 6. API 映射（增量）

> **契约真源：** [管理后端 final-spec §4](./2026-07-27-admin-backend-final-spec.md)

| 能力 | API（目标） | 阶段 |
|------|-------------|------|
| 总览聚合 | `GET /admin/overview` | C0 |
| 插件列表 | `GET /admin/domains`（扩展字段） | C0 |
| 审计导出 | `GET /admin/audit/export` | 已有 |
| 配置只读 | `GET /admin/config` | C0 |
| 配置热写 | `PUT /admin/config/{key}` | **C2+** |
| Tools 目录 | `GET /admin/tools` | C1 |
| Tools 试调 | `POST /admin/tools/{name}/invoke` | C1（默认关） |
| Run 列表 | `GET /admin/runs` | C1 |
| Prompts | `/prompts/*` | C2 |
| 用量 | `GET /admin/usage/tokens` | C3 |
| 知识状态 | `GET /admin/knowledge/status`（① 提供） | C4 |

所有写接口：`admin:*` + 审计。

---

## 7. 分期与验收

| 期 | 侧栏 / 页面 | 验收（说人话） |
|----|-------------|----------------|
| **C0** | 总览、调试、插件、配置只读 | 看见接了啥、通不通、24h Run/错误；**无 Token、无写配置** |
| **C1** | + 运行与回放 `/runs`、Tools `/tools` | 工具目录与权限矩阵；Run 列表可筛可回放；试调默认关 |
| **C2** | + Prompts、配置档 A 可写 | 改 Prompt 与热配并审计 |
| **C3** | + 模型与用量 | `tenant`/`route`/`model` Token 分组；无数据不造假 |
| **C4** | + 知识后端 | 展示 status 与入库任务（只读） |

**C0 明确不另起应用：** 改 `apps/web` 路由与侧栏即可。

---

## 8. 与①③的边界

| 不做 | 原因 |
|------|------|
| 在控制台做报告排版 / 地图 | 属业务前端或插件自有 UI |
| 在控制台实现检索算法 | 属①知识后端 |
| 把客户业务菜单挂进侧栏 | 破坏「只服务框架」定位 |
| 在 Plan7 里做 `demo_datasource` 等样板插件 | 属 **③ 业务插件轨**，见 [管理 Spec §10](./2026-07-27-admin-backend-final-spec.md) |

业务插件（③）只出现在「插件列表 / 调试选 route」；能力细节由插件自己的 API/文档负责。

---

## 9. 风险

| 风险 | 缓解 |
|------|------|
| 配置热写导致线上误改 | 分档；写审计；关键项确认框；可回滚 |
| Token 统计不准 | C3 前先定 Gateway 上报契约；无数据不显示假数 |
| 控制台与业务前端混淆 | 文档与导航文案固定「AI 控制台 / 框架管理」 |

---

## 10. 成功标准

- [ ] 集成方仅用控制台即可完成：选插件联调、看事件、看插件与配置只读  
- [ ] 管理员能区分热配 / 启动项 / 密钥三档  
- [ ] 无 `admin:*` 无法写配置与 Prompt  
- [ ] 不出现业务前端信息架构  
