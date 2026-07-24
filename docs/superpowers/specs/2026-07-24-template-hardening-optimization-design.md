# Agent-Base 全面优化设计 — 模板硬化 + 生产能力（两期）

> 状态：**二次审阅修订完成；待用户确认后进入实施计划**  
> 日期：2026-07-24  
> 仓库：`Agent-Base`  
> 前置：主设计 [2026-07-23-agent-ai-base-design.md](./2026-07-23-agent-ai-base-design.md)、[code-structure](./2026-07-23-code-structure.md)  
> 决策摘要：路径 D · 扩展事件稳定集+`x.*` · 长期 `demo_tools` · **build_event=Option B** · 扩展通道=状态约定

---

## 1. 结论

| 期 | 名称 | 一句话 |
|----|------|--------|
| **一期** | 模板硬化 | 契约单源、工具 SSE 防腐、长期 `demo_tools`、组装根瘦身；**不做**分布式锁 |
| **二期** | 生产能力 | Redis（优先）锁/cancel、就绪探针、可观测与 JWKS TTL；文档写死多副本前提 |

**落地顺序（硬前置）：**

0. 对齐 `contracts.md`（含 cancel `data`、废除「任意透传」）  
1. OutboundFragment + **Option B** 双 builder + mapper 补 `tool_result` + 最小 `step_update`  
2. `langgraph_runtime`：`on_tool_end` + 扩展抽取 + 最小 step 映射  
3. 挂 `demo_tools`（无 LLM；含 ≥1 个 `x.demo_tools.*`）  
4. 瘦 lifespan + 收敛 `app.state`  

第 2 步是第 3 步的前置：无 `tool_result` / 扩展通道则无法验收 `demo_tools`。

### 1.1 「零改 core」措辞

| 说法 | 含义 |
|------|------|
| **本期（一期硬化）** | **会改** `packages/core` |
| **硬化完成后** | 再挂第三域起：只改 `domains/*` + `bootstrap`（及文档/web） |
| **硬禁令** | core 不得出现业务域名 / 业务节点名硬编码（如 `demo_tools`、`echo_node`） |

---

## 2. 目标与非目标

### 2.1 一期目标

1. **契约单源**：`contracts.md` 与实现一致（稳定九类 + `x.*` 规则）。  
2. **防腐闭合**：Fragment；`tool_call`/`tool_result`；最小 `step_update` 映射。  
3. **扩展通道**：`outbound_extensions` 状态约定；应用层校验 `x.*`；**域不得持有 `EventSink`**。  
4. **样板域** `demo_tools`（无 LLM）。  
5. **组装根瘦身** + `app.state` 白名单。  
6. **修线上缺口**：cancel 事件补 `data`；禁止 host `r-host` 旁路。  
7. **回归** echo / 409 / cancel / auth。

### 2.2 一期非目标

- 分布式锁 / 跨进程 cancel、多副本安全宣称  
- 完整 PKCE↔Authentik、产品业务迁入、Celery  
- `demo_tools` 依赖 LLM  
- 新增 `ensure_route` 之类预检 API（保持 `UnknownRoute` 异常映射即可）

### 2.3 二期目标（概要）

分布式 Redis 锁/cancel、`/ready`、JWKS TTL、可配置 hooks/`trace_id`；文档纪律：未换锁不得水平扩展。

### 2.4 一期成功标准

- `demo_tools` 流：`start` → `tool_call` → `tool_result` → ≥1×`x.demo_tools.*` → `done`（text/step **不强制**）  
- `cancel_requested`/`cancelled` 的 `data` 含 `thread_id`+`run_id`  
- 非法 `x.*`（如 `X.UPPER.*`、`x.`）被拒绝  
- `sequence` 仅 lifecycle；无 `r-host`/`sequence=0`  
- `app.state` 不再暴露 `locks`/`cancels`/`graphs`/`tools`/`input_builders` 给生产路径  
- core 无 `demo_tools`；CI 无外部 LLM  

---

## 3. 契约与事件模型

### 3.1 两类事件

| 类 | 规则 | 示例 |
|----|------|------|
| 稳定集 | 九类固定 | `start`…`cancelled` |
| 扩展集 | `^x\.[a-z][a-z0-9_]*\.[a-z0-9_.]+$` | `x.demo_tools.finished` |

**必须改** `docs/contracts.md` §2 末句：删除「type 可为自定义字符串；核心原样透传」；改为本节规则。

### 3.2 OutboundFragment

```text
OutboundFragment:
  type: str
  data: dict = {}
  step: str | None = None
  status: str | None = None
```

Runtime/mapper **只产 Fragment**，不写权威 `sequence`/`event_id`。

### 3.3 Builder：Option B（已拍板）

| 函数 | 职责 |
|------|------|
| `build_event(...)` | **仅**稳定九类；未知稳定 type → 错误 |
| `build_extension_event(...)` | **仅**合法 `x.*`；非法前缀 → 明确错误（禁止 silent drop） |

`RunLifecycle` 根据 Fragment.type 选择调用哪个 builder，再写入 `run_id`/`sequence`/`event_id`/`trace_id`/`timestamp` 后 `emit`。

**不采用 Option A**（单函数兼两种语义）。

### 3.4 cancel / error 终端保证

- `cancel_requested` / `cancelled`：`data` **必须**含 `thread_id`、`run_id`（修当前实现遗漏；加测试钉死）。  
- host **禁止** `run_id="r-host"` / `sequence=0` 旁路。  
- `start_stream` 使用 **`terminal_sent`（或 `error_sent`）标志**：若已 `try_acquire` 且流应对客户端有收尾，则在异常路径保证发出 `error` **或** cancel 对 **或** `done` 之一后再 `sink.close()`，避免「连接断了却无终端事件」。`try_acquire` 失败（`ThreadBusy`）仍只抛异常、不发 SSE。

### 3.5 LangGraph 防腐

| 信号 | Fragment |
|------|----------|
| chat stream | `text_delta` |
| `on_tool_start` | `tool_call` |
| `on_tool_end` | `tool_result`（`name`/`ok`/`tool_call_id`/`summary` 对齐 contracts） |
| `on_chain_start` / 合适的 end | **最小** `step_update`（`status=running|done`）；**demo_tools 验收不强制出现** |
| `outbound_extensions` | `x.*`（校验在应用层 builder） |
| 未捕获异常 | lifecycle → `error` |

`event_mapper` 须新增 `map_tool_result`；runtime 须处理 `on_tool_end`。

### 3.6 扩展通道（状态约定，已拍板）

1. State 含 `outbound_extensions: list[{type, data}]`。  
2. Runtime 在适当时机读出并 yield Fragment（type 原样带上）。  
3. Lifecycle 用 `build_extension_event` 校验并编号。  

**禁止：** 域持有 `EventSink`；core 写死域名；默认 **不采用** runtime `event_hook` callback（避免第二推流路径）。  
仅当状态约定在实现中不可行时，才允许降级为极薄 port（仍禁域名、禁域持 sink）——须在计划中显式变更，不得默默改。

---

## 4. `demo_tools` 域

### 4.1 布局

```text
apps/api/domains/demo_tools/
  state.py / tools.py / graph.py / bootstrap.py / README.md
```

### 4.2 约束

- **无** ChatModel / **无** `LLM_API_KEY` 依赖。  
- 真绑定 tool，稳定产生 `tool_call` + `tool_result`。  
- 结束前写入 ≥1 条 `x.demo_tools.*` 到 `outbound_extensions`。  
- `step_update`/`text_delta`：不强制。

### 4.3 挂载与门禁

`register_all` 注册 echo + demo_tools；扫描 core 无 `demo_tools` / 业务节点硬编码。

### 4.4 Web（软）

文档与 Contracts 说明 `demo_tools` 与 `x.*`；推荐 route 下拉与 `x.*` 折叠（不进硬红线）。

---

## 5. 组装根与宿主

| 项 | 拍板 |
|----|------|
| Fake | 迁出 lifespan；仅测试/env 开关 import |
| 未知 route | lifecycle/`graphs.get` → `UnknownRoute`；路由只映射 400；**不**新增 `ensure_route` |
| `app.state` | **生产允许：** `run_lifecycle`、`settings`。**禁止暴露：** `locks`/`cancels`/`graphs`/`tools`/`input_builders`。测试注册 double：用 lifespan 测试钩子或临时 fixture，不以 locks 抢锁为主路径 |
| hooks | `hooks_backend=noop\|logging` |
| Postgres | **`pg_dsn` 优先**；若空则 fallback `pg_host/port/database/user/password` 拼接；工厂只收最终 DSN 字符串；文档标注 `pg_dsn` 为推荐 |
| 原则 | 唯一 `new` 适配器 = lifespan；`public` 不 new |

### 5.1 adapters 同层依赖

**允许** `agent_base_core.adapters.* → adapters.*`（如同 `langgraph_runtime` → `event_mapper`）。  
实施时在 [code-structure](./2026-07-23-code-structure.md) 补一句，避免与「adapters 只依赖 ports/protocol」表述冲突。

---

## 6. 二期（不阻塞一期）

Redis 锁/cancel、`/ready`、JWKS TTL、可配置 hooks/`trace_id`；文档：未换锁不得水平扩展。

---

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| `x.*` 噪音 | 调试台折叠（软） |
| LangGraph 版本差 | 字段级映射测 |
| `app.state` 收敛破测 | 一期改夹具；CI 分目录 |
| 误读零改 core | §1.1 |
| 偷偷改用 callback | §3.6 禁止默认；变更须改本规格 |

---

## 8. 验收清单

### 一期

- [ ] `contracts.md`：稳定九类 + `x.*`；无「任意自定义透传」  
- [ ] `build_event` 仅稳定九类；`build_extension_event` 校验 `x.*`；非法前缀失败测例  
- [ ] OutboundFragment；lifecycle 唯一编号  
- [ ] `map_tool_result` + `on_tool_end`  
- [ ] 最小 `step_update` 映射存在（demo 验收不强制看到）  
- [ ] cancel 事件 `data` 含 `thread_id`+`run_id`（测例钉死）  
- [ ] 终端事件保证（`terminal_sent` / 等价）  
- [ ] `outbound_extensions` 通道；core 无域名  
- [ ] `demo_tools` 无 LLM；流验收通过  
- [ ] lifespan 无 Fake 类；`app.state` 不暴露 locks/cancels/graphs/tools/input_builders  
- [ ] echo/409/cancel/auth 回归；门禁绿  

### 二期

- [ ] 跨进程 409/cancel；`/ready`；JWKS TTL；hooks 可切换  

---

## 9. 与主设计关系

不改 ADR 方向；P7 多副本锁归二期。下一步写实施计划：  
`docs/superpowers/plans/2026-07-24-template-hardening-optimization-implementation.md`。

---

## 10. 决策与修订记录

### 10.1 头脑风暴

| 项 | 选择 |
|----|------|
| 节奏 | 先硬化再生产 |
| 扩展事件 | 稳定集 + `x.*` |
| 第二域 | 长期 `demo_tools` |
| 路径 | 契约先行竖切 |

### 10.2 第一次方案审阅修订

零改 core 措辞、Fragment、状态约定、无 LLM、未知 route、app.state 白名单。

### 10.3 第二次系统架构审阅修订（本版）

| 项 | 决定 |
|----|------|
| build_event | **Option B**（稳定 / 扩展分函数） |
| 扩展通道 | 维持状态约定；**禁止**域持 EventSink；不默认 callback |
| step_update | 一期**做最小映射**；demo **验收不强制** |
| cancel data | 标为线上 bug，一期必修+测 |
| 终端事件 | `terminal_sent`（或等价）保证 |
| DSN | `pg_dsn` 优先 + 五字段 fallback |
| adapters→adapters | **允许**，补 code-structure |
| ensure_route | **不做** |
| 实施顺序 | 明确 0→4 步硬前置 |
| 验收 | 并入非法 `x.*`、cancel data、app.state 收敛等项 |
