# Agent-Base 全面优化设计 — 模板硬化 + 生产能力（两期）

> 状态：**已写入，待用户审阅本文件后进入实施计划**  
> 日期：2026-07-24  
> 仓库：`Agent-Base`  
> 前置：主设计 [2026-07-23-agent-ai-base-design.md](./2026-07-23-agent-ai-base-design.md)、架构核验结论（sound with caveats）  
> 决策摘要：路径 D（先硬化再生产）· 扩展事件 B（稳定集 + `x.*`）· 第二域 A（长期 `demo_tools`）

---

## 1. 结论

在底座主路径已可用的前提下，用**两期**还清架构债，而不是再堆功能：

| 期 | 名称 | 一句话 |
|----|------|--------|
| **一期** | 模板硬化 | 契约单源、工具 SSE 防腐、长期 `demo_tools`、组装根瘦身；**不做**分布式锁 |
| **二期** | 生产能力 | Redis（优先）锁/cancel、就绪探针、可观测与 JWKS TTL；文档写死多副本前提 |

落地顺序采用**契约先行竖切**：先钉 `contracts` + `build_event` + runtime 映射 → 再挂 `demo_tools` → 再瘦 `lifespan` → 二期换分布式适配器。

---

## 2. 目标与非目标

### 2.1 一期目标

1. **契约单源**：`docs/contracts.md` 与 `protocol/events.build_event` 对「稳定九类 + `x.<domain>.*`」规则一致。  
2. **防腐闭合**：LangGraph → SSE 至少覆盖 `tool_call` / `tool_result`，并支持合理的 `step_update`。  
3. **第二域样板**：长期示例域 `apps/api/domains/demo_tools`，**零改 `packages/core`** 即可注册运行。  
4. **组装根瘦身**：Fake runtime 迁出 `lifespan.py`；收敛 `app.state`；settings 驱动 hooks / DSN。  
5. **回归**：echo / 409 / cancel / auth 既有测试保持绿。

### 2.2 一期非目标

- Redis / PG advisory 分布式锁与跨进程 cancel  
- 多副本「水平扩展安全」宣称  
- Web 完整 PKCE ↔ Authentik 联调（可后置）  
- 产品仓业务迁入、Celery 默认路径  

### 2.3 二期目标（概要）

- 在**不改编排流程**的前提下，为 `ThreadLock` / `RunCancelRegistry` 增加 Redis（优先）适配器，settings 切换。  
- `/ready` 与文档「未换分布式锁前禁止多副本」。  
- JWKS 缓存 TTL；hooks / `trace_id` 入站可配置。

### 2.4 一期成功标准（可验收）

- 仅改 `domains/*` + `domains/bootstrap.py`（及文档/web 文案）即可使用 `route=demo_tools`。  
- 调试台或集成测可见：`start` → `tool_call` → `tool_result` →（可选 text/step）→ 至少一个 `x.demo_tools.*` → `done`。  
- `build_event` 接受合法 `x.*`，拒绝非法 type；`sequence` 仅由 `RunLifecycle` 分配。  
- 生产 `lifespan.py` 内无 Fake 类定义；测试不依赖 `app.state.locks` 做主路径。

---

## 3. 契约与事件模型

### 3.1 两类事件

| 类 | 规则 | 示例 |
|----|------|------|
| 稳定集 | 固定九类：`start` / `step_update` / `text_delta` / `tool_call` / `tool_result` / `done` / `error` / `cancel_requested` / `cancelled` | 产品对照、调试台默认解析 |
| 扩展集 | type 必须匹配 `^x\.[a-z][a-z0-9_]*\.[a-z0-9_.]+$` | `x.demo_tools.finished` |

### 3.2 `build_event` 与序号所有权

- 稳定集：type ∈ 九类。  
- 扩展集：合法 `x.*` 允许出站；非法前缀 → 明确错误（禁止 silent drop）。  
- 公共信封字段：`type` / `run_id` / `event_id` / `sequence` / `trace_id` / `timestamp` / `data`（及可选 `step`/`status`）。  
- **`sequence` / `event_id` / 运行元数据仅由 `RunLifecycle` 写入**；runtime / mapper 只产出语义载荷（`type` + `data` 等），不再产生权威序号。  
- `cancel_requested` / `cancelled` 的 `data` 须含 `thread_id`、`run_id`（对齐 contracts 样例）。  
- host 层兜底 `error` 必须走同一 builder + 同一序号规则，禁止 `sequence=0` / `run_id=r-host` 旁路信封。

### 3.3 LangGraph 防腐（一期最小闭合）

| 信号 | 出站 |
|------|------|
| chat model stream | `text_delta` |
| tool start | `tool_call` |
| tool end | `tool_result`（含 `ok` / `summary` 等与 contracts 对齐字段） |
| 节点结束（可选） | `step_update` |
| 未捕获异常 | `error`（lifecycle） |
| 域扩展样例 | ≥1 个 `x.demo_tools.*`（由域或 mapper 钩子发出，核只校验前缀） |

文档必须删除或改写「任意自定义 type 无条件透传」的表述，改为本节规则。

---

## 4. `demo_tools` 域

### 4.1 布局

```text
apps/api/domains/demo_tools/
  state.py
  tools.py      # ≥1 真实 tool，图内真正绑定
  graph.py
  bootstrap.py
  README.md     # 与 echo 差异、复制指引
```

### 4.2 行为

- `route="demo_tools"`  
- 流：`start` → `tool_call` → `tool_result` → 可选 `text_delta`/`step_update` → `x.demo_tools.*` → `done`  
- 在 `domains/bootstrap.register_all` 与 `echo` 一并注册  
- **禁止** `packages/core` 出现 `demo_tools` 字样（门禁或测试扫描）

### 4.3 Web（一期软要求）

- 默认 route 可为 `echo`；文档与 Contracts 页说明 `demo_tools`  
- 可选：调试台 route 下拉（推荐但非硬门槛）

---

## 5. 组装根与宿主收敛

| 项 | 设计 |
|----|------|
| Fake runtime | 迁出 `lifespan.py`（如 `apps/api/testing/fake_runtime.py` 或仅 tests）；仅当 `AGENT_BASE_FAKE_RUNTIME=1` 时由 lifespan import |
| `app.state` | 对外以 `run_lifecycle` + `settings` 为主；未知 route 通过 lifecycle/public（如 `ensure_route`）或统一异常映射到 400，避免路由层直接依赖 registry 作为长期模式 |
| hooks | `settings` 选择 `noop` / `logging` |
| Postgres DSN | `settings` 提供完整 DSN；工厂只接收字符串 |
| 原则 | 唯一 `new` 适配器处仍是 lifespan；`public` 不 new |

测试：busy/cancel 用可阻塞/可取消的 fake runtime + 公开 API，不把 `app.state.locks` 当主夹具。

---

## 6. 二期生产能力（概要，不阻塞一期计划）

| 能力 | 要点 |
|------|------|
| 分布式锁/cancel | 现有 ports 不变；新增 Redis（优先）适配器；`lock_backend=inprocess\|redis` |
| 探针 | `/health` = liveness；`/ready` = checkpointer（及可选 Redis） |
| 可观测 | 可配置 LoggingHooks；可选入站 `trace_id`；JWKS TTL |
| 文档 | 明确：未换分布式锁前不得水平扩展聊天入口 |

---

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| `x.*` 导致前端噪音 | 调试台对未知 `x.*` 折叠；稳定九类优先 |
| LangGraph 版本差异 | contracts 字段级测试钉死映射 |
| `app.state` 收敛破坏测试 | 一期同步改夹具，CI 红 |
| 误把一期模板当多副本方案 | README/deploy 醒目警告；二期才提供适配器 |

---

## 8. 验收清单

### 一期

- [ ] `contracts.md` + `build_event`：稳定九类 + `x.*` 一致  
- [ ] runtime：`tool_call` / `tool_result`（+ 合理 `step_update`）  
- [ ] `demo_tools` 进仓；零改 core 可挂  
- [ ] lifespan 无 Fake 类定义；`app.state` 收敛  
- [ ] echo / 409 / cancel / auth 回归绿  
- [ ] import-linter + `import_scan_core` 绿；core 无 `demo_tools`  

### 二期

- [ ] 分布式锁下跨进程 409 / cancel 可测  
- [ ] `/ready` + 多副本前提文档  
- [ ] JWKS TTL；hooks/settings 可切换  

---

## 9. 与主设计关系

- 不修改 ADR-1～10 的方向；补齐实现缺口（SSE 防腐、契约单源、组装根卫生）。  
- P7 中的多副本锁/OTel 等归入本规格**二期**，与「模板宣布可用」解耦。  
- 实施时另写 `docs/superpowers/plans/2026-07-24-template-hardening-optimization-implementation.md`（writing-plans），一期与二期可拆 plan 或同一 plan 分 Task 段。

---

## 10. 头脑风暴决策记录

| 问题 | 选择 |
|------|------|
| 优化节奏 | D：先模板硬化，再生产能力 |
| 一期通过线 | D：假域+工具 SSE+契约单源+组装根瘦身；不做 Redis 锁 |
| 扩展事件 | B：稳定集 + `x.<domain>.*` |
| 第二域落仓 | A：长期示例域 `demo_tools` |
| 实施路径 | 契约先行竖切（非样板倒逼、非多轨并行） |
