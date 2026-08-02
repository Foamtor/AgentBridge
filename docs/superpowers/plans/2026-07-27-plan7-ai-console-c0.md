# Plan7 — AI 控制台 C0（升级 apps/web）

> **状态：** 历史计划；AI 控制台基础能力已实现，当前首发以 [v0.1.0 Plan](./2026-08-01-p3a-open-source-release-preparation.md) 的黄金案例呈现为准。
>
> **设计稿：** [../specs/2026-07-27-ai-admin-console-design.md](../specs/2026-07-27-ai-admin-console-design.md)  
> **契约真源：** [../specs/2026-07-27-admin-backend-final-spec.md](../specs/2026-07-27-admin-backend-final-spec.md)  
> **归属：** 历史管理后台设计记录。
>
> **依赖：** Plan1–5（部分管理 API、调试台已有）；与 Plan6 **软并行**（C0 不依赖真知识后端）  
> **策略：** **升级现有 `apps/web`**，不另起 `apps/admin`

---

## C0 范围（本 Plan 只做 C0）

| 项 | 交付 |
|----|------|
| 前置 | Run 投影（§6.2）、域 catalog（§6.3） |
| 信息架构 | 侧栏：总览 / 调试 / 插件 / 配置（只读） |
| 总览 | `GET /admin/overview`：backend 探测 + infra_ready + 24h Run/错误 |
| 调试增强 | 审批入口、Run 回放入口、citation 高亮；route 动态来自 domains |
| 插件列表 | `GET /admin/domains` → `{ "domains": [...] }` |
| 配置只读 | `GET /admin/config`：§5.3 manifest；档 A 为空 |

**不做（C1+）：** 热写配置、Prompt CRUD UI、Token 图表、知识入库面板、`GET /admin/runs`、Tools 试调。

> **收敛：** C0 严禁热写。见 [方案收敛](../specs/2026-07-27-scheme-convergence.md)。

---

## 任务

### T0 — C0 前置（底座 + 组装）

> 管理 Spec §6.2 / §6.3；**阻塞** T1–T4 中与 overview / domains / 24h 统计相关的项。

- [ ] T0.1 **Run 投影**：`run_lifecycle` / `project_turn` upsert 增加 `route`、`started_at`、`ended_at`
- [ ] T0.2 **测试**：流式跑完后 `GET /runs/{id}` 含 `route` + `started_at`
- [ ] T0.3 各域 `bootstrap.py` 增加 `DOMAIN_META = {"description": "..."}`
- [ ] T0.4 `lifespan.py` 构建 `app.state.domain_catalog`（只读快照）；admin **不**直接暴露 `GraphRegistry`
- [ ] T0.5 辅助：`apps/api/admin/catalog.py`（或同级）投影 tools + graphs + meta

### T1 — 管理 API（C0）

- [ ] T1.1 `GET /admin/overview`：`admin:read`；infra_ready 复用 ready 逻辑；backend 独立探测（Spec §4.1）
- [ ] T1.2 `GET /admin/config`：`admin_config.py`；按 §5.3 manifest 投影 Settings；tier A 空
- [ ] T1.3 `GET /admin/domains`：返回 `{ "domains": catalog }`（**破坏性**：替换裸数组）
- [ ] T1.4 权限与测试：overview/config/domains；密钥不明文；无权限 403

### T2 — `apps/web` 路由与侧栏

- [ ] T2.1 侧栏路由：`/` 总览 · `/debug` 调试 · `/domains` 插件 · `/config` 配置；文案「AI 控制台」
- [ ] T2.2 **总览页**：5 区（插件 / LLM / Knowledge / infra_ready / 24h Run）
- [ ] T2.3 **配置只读页**：B/C 分组；C 档 `●已配置 / ○未配置`；无 tier A 或显示「C2+ 开放」
- [ ] T2.4 **插件列表页**：表格（name / desc / tools / permissions / graph）
- [ ] T2.5 权限守卫：无 admin 权限时 403 提示

### T3 — 调试增强

- [ ] T3.1 `SessionBar` route 选项改为 `GET /admin/domains` 动态加载
- [ ] T3.2 SSE：`x.bridge.citation` 高亮（非仅折叠在 x.*）
- [ ] T3.3 审批：对接 `/approvals/*`（`approval:decide`）
- [ ] T3.4 run_id 可点击跳转 `/runs/{id}/events`（或内嵌回放面板）

### T4 — 文档

- [ ] T4.1 控制台说明链到 ai-admin-console-design.md
- [ ] T4.2 README / design-tracks 链到 admin-backend-final-spec

### T5 — 门禁

- [ ] T5.1 `pytest`：admin API + Run 投影 + domains 对象形态
- [ ] T5.2 `apps/web` build 无 error
- [ ] T5.3 冒烟：总览 → 配置 → 插件 → 调试发流 → overview 24h 计数 > 0

---

## 后续（不在本 Plan）

- **C1** Tools + `GET /admin/runs` + `POLICY_MATRIX_ROLES` 矩阵 · **C2** Prompt + 热配 · **C3** Token · **C4** 知识面板

### 已迁出：T7 `demo_datasource`

> **归属 ③ 业务插件轨**，非管理后端 C0 范围。样板插件单独立项（见 [业务插件 Spec](../specs/2026-07-27-business-plugins-final-spec.md)），勿与本 Plan 混排。
