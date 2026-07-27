# Plan7 — AI 控制台 C0（升级 apps/web）

> **状态：** 待实施  
> **设计稿：** [../specs/2026-07-27-ai-admin-console-design.md](../specs/2026-07-27-ai-admin-console-design.md)  
> **归属：** 设计三类之 **② 管理后台**（见 [design-tracks.md](../../design-tracks.md)）  
> **依赖：** Plan1–5（管理 API、调试台已有）；与 Plan6 **软并行**（C0 不依赖真知识后端）  
> **策略：** **升级现有 `apps/web`**，不另起 `apps/admin`

---

## C0 范围（本 Plan 只做 C0）

| 项 | 交付 |
|----|------|
| 信息架构 | 侧栏：总览 / 调试 / 插件 / 配置（只读） |
| 总览 | 插件数、LLM/知识 backend 只读、`/ready` 摘要、**24h Run/错误**（`GET /admin/overview`） |
| 调试增强 | 审批入口、Run 回放入口、citation 高亮（有则显示） |
| 插件列表 | 调用扩展后的 `GET /admin/domains` |
| 配置只读 | `GET /admin/config`：分档展示 A/B/C（C 仅状态） |

**不做（C1+）：** 热写配置、Prompt CRUD UI、Token 图表、知识入库面板。  

> **收敛：** C0 严禁热写。见 [方案收敛](../specs/2026-07-27-scheme-convergence.md)。
---

## 任务

### T1 — `GET /admin/config`（只读）

- [ ] T1.1 `apps/api/routes/admin_config.py`：从 Settings 投影，按 tier A/B/C 分类
- [ ] T1.2 tier=C 项 `value=null, configured=true/false`；响应格式见 [管理 Spec §4.1](../specs/2026-07-27-admin-backend-final-spec.md)
- [ ] T1.3 权限守卫 `admin:config`（或 `admin:read`）
- [ ] T1.4 测试：有权限 200 + 密钥不明文；无权限 403

### T2 — 扩展 `GET /admin/domains`

- [ ] T2.1 返回 `tools[]`、`required_permissions[]`、`graph_registered`；格式见管理 Spec §4.1
- [ ] T2.2 测试：至少 `demo_rag` / `demo_tools` 出现且字段完整

### T3 — `apps/web` 路由与侧栏

- [ ] T3.1 侧栏路由：`/` 总览 · `/debug` 调试 · `/domains` 插件 · `/config` 配置
- [ ] T3.2 **总览页**：4 卡片（插件数 / LLM Backend / Knowledge Backend / ready 摘要）
- [ ] T3.3 **配置只读页**：三分组渲染 A/B/C；C 档 `●已配置 / ○未配置`
- [ ] T3.4 **插件列表页**：表格（name / desc / tools / permissions / graph 状态）
- [ ] T3.5 权限守卫：无 admin 权限时显示 403 提示而非空白页

### T4 — 调试增强

- [ ] T4.1 SSE 面板增加 citation 高亮（`x.bridge.citation` 事件特殊渲染）
- [ ] T4.2 审批待处理列表：有 `awaiting_approval` 的 run 显示审批按钮
- [ ] T4.3 run_id 可点击跳转到回放（`/runs/{id}/events`）

### T5 — 文档

- [ ] T5.1 控制台使用说明链到 ai-admin-console-design.md
- [ ] T5.2 README 文档地图加 admin-backend-final-spec

### T6 — 门禁

- [ ] T6.1 `pytest` admin API 测试通过
- [ ] T6.2 `apps/web` build 无 error
- [ ] T6.3 E2E 冒烟：启动 → 总览页 → 配置页 → 插件页均可加载

---

## 后续（不在本 Plan）

- **C1** Tools + Run 列表页 · **C2** Prompt + 热配 · **C3** Token · **C4** 知识面板（可接 Plan6 status API）

### 已迁出：T7 `demo_datasource`

> **归属 ③ 业务插件轨**，非管理后端 C0 范围。样板插件单独立项（见 [业务插件 Spec](../specs/2026-07-27-business-plugins-final-spec.md)），勿与本 Plan 混排。
