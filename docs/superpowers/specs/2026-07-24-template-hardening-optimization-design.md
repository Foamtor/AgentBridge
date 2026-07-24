# Agent-Base 全面优化设计 — 模板硬化 + 生产能力（两期）

> 状态：**已按方案审阅修订；待用户确认后进入实施计划**  
> 日期：2026-07-24（修订同日）  
> 仓库：`Agent-Base`  
> 前置：主设计 [2026-07-23-agent-ai-base-design.md](./2026-07-23-agent-ai-base-design.md)、架构核验结论（sound with caveats）  
> 决策摘要：路径 D（先硬化再生产）· 扩展事件 B（稳定集 + `x.*`）· 第二域 A（长期 `demo_tools`）  
> 修订要点：澄清「零改 core」含义、OutboundFragment 通道、无 LLM 样板图、未知 route 策略、`app.state` 白名单

---

## 1. 结论

在底座主路径已可用的前提下，用**两期**还清架构债，而不是再堆功能：

| 期 | 名称 | 一句话 |
|----|------|--------|
| **一期** | 模板硬化 | 契约单源、工具 SSE 防腐、长期 `demo_tools`、组装根瘦身；**不做**分布式锁 |
| **二期** | 生产能力 | Redis（优先）锁/cancel、就绪探针、可观测与 JWKS TTL；文档写死多副本前提 |

落地顺序采用**契约先行竖切**：先钉 `contracts` + `build_event` + OutboundFragment + runtime 映射 → 再挂 `demo_tools` → 再瘦 `lifespan` → 二期换分布式适配器。

### 1.1 「零改 core」措辞（重要）

| 说法 | 含义 |
|------|------|
| **本期（一期硬化）** | **会改** `packages/core`（`x.*`、`tool_result`、Fragment、序号所有权等） |
| **硬化完成后** | 再挂**第三个及以后**业务域时，只改 `domains/*` + `bootstrap`（及文档/web），**零改 core** |
| **硬禁令** | core 源码与测试中**不得出现**业务域名字符串（含 `demo_tools`、`echo_node` 类硬编码节点名） |

---

## 2. 目标与非目标

### 2.1 一期目标

1. **契约单源**：改写 `docs/contracts.md`（删除「任意 type 无条件透传」）；与 `build_event` 对「稳定九类 + `x.<domain>.*`」一致。  
2. **防腐闭合**：引入 **OutboundFragment**；LangGraph → Fragment 至少覆盖 `tool_call` / `tool_result`；`step_update` 可选发出。  
3. **扩展事件通道（通用）**：域可通过**状态约定**产出 `x.*` Fragment；core 只校验前缀与信封，**不写任何域名**。  
4. **第二域样板**：长期示例域 `apps/api/domains/demo_tools`（**无 LLM**，CI 零外部 key）。  
5. **组装根瘦身**：Fake 迁出 lifespan；`app.state` 白名单；settings 驱动 hooks / DSN。  
6. **回归**：echo / 409 / cancel / auth 保持绿。

### 2.2 一期非目标

- Redis / PG advisory 分布式锁与跨进程 cancel  
- 多副本「水平扩展安全」宣称  
- Web 完整 PKCE ↔ Authentik 联调（可后置）  
- 产品仓业务迁入、Celery 默认路径  
- `demo_tools` 强制依赖 ChatModel / API key  

### 2.3 二期目标（概要）

- 在**不改编排流程**的前提下，为 `ThreadLock` / `RunCancelRegistry` 增加 Redis（优先）适配器，settings 切换。  
- `/ready` 与文档「未换分布式锁前禁止多副本」。  
- JWKS 缓存 TTL；hooks / `trace_id` 入站可配置。

### 2.4 一期成功标准（可验收）

- 硬化合并后：仅改域目录 + `bootstrap` 即可再挂新域（证明方式：`demo_tools` 自身不进 core）。  
- 集成测 `route=demo_tools`：`start` → `tool_call` → `tool_result` →（**不强制** text/step）→ ≥1 个合法 `x.demo_tools.*` → `done`。  
- `build_event`：稳定九类 + 合法 `x.*` 通过；非法 type 失败。  
- `sequence` 仅由 `RunLifecycle` 分配；无 `r-host` / `sequence=0` 旁路。  
- `lifespan.py` 无 Fake 类定义；测试主路径不摸 `app.state.locks`。  
- CI 无外部 LLM；import-linter + 包名/域名扫描绿。

---

## 3. 契约与事件模型

### 3.1 两类事件

| 类 | 规则 | 示例 |
|----|------|------|
| 稳定集 | 固定九类：`start` / `step_update` / `text_delta` / `tool_call` / `tool_result` / `done` / `error` / `cancel_requested` / `cancelled` | 产品对照、调试台默认解析 |
| 扩展集 | type 必须匹配 `^x\.[a-z][a-z0-9_]*\.[a-z0-9_.]+$` | `x.demo_tools.finished` |

实施时同步修改 `docs/contracts.md` §2 末句，改为本节规则（禁止再写「任意自定义字符串无条件透传」）。

### 3.2 OutboundFragment（中间形态）

Runtime / mapper / 域扩展通道**不得**直接构造带权威 `sequence` 的完整信封。统一产出：

```text
OutboundFragment:
  type: str                 # 稳定九类或合法 x.*
  data: dict                # 默认 {}
  step: str | None          # 可选
  status: str | None        # 可选
```

`RunLifecycle` 负责：`build_event(type, run_id=…, sequence=…, trace_id=…, data=…, step=…, status=…)` → `EventSink.emit`。

既有 `map_text_delta` / `map_tool_call` 改为返回 Fragment（或等价 dict），由 lifecycle 套信封；**删除** mapper 内对 `sequence`/`event_id` 的权威赋值。

### 3.3 `build_event` 与 cancel/error

- 稳定集：type ∈ 九类。  
- 扩展集：合法 `x.*` 允许；非法 → 明确错误（禁止 silent drop）。  
- `cancel_requested` / `cancelled` 的 `data` 必须含 `thread_id`、`run_id`。  
- host 兜底错误：若在 stream 已开始后失败，须经 lifecycle 发 `error` Fragment/事件；**禁止** `run_id="r-host"`、`sequence=0` 旁路 JSON。

### 3.4 LangGraph 防腐（一期最小闭合）

| 信号 | 出站 Fragment |
|------|----------------|
| chat model stream | `text_delta` |
| tool start | `tool_call` |
| tool end | `tool_result`（字段对齐 contracts：`name` / `ok` / `tool_call_id` / `summary` 等） |
| 节点结束 | `step_update`（**可选**；验收不强制） |
| 状态中的扩展队列 | 见 §3.5 → `x.*` |
| 未捕获异常 | lifecycle → `error` |

### 3.5 扩展事件通道（写死，通用，无域名）

**选定机制：状态约定 + runtime 通用抽取（推荐实现）。**

1. 图 State（或 `extra`/返回值约定）可含：

   ```text
   outbound_extensions: list[{ "type": "x....", "data": {...} }]
   ```

2. `LangGraphRuntime` 在合适时机（如相关 `on_chain_end` / 流结束前）读取该列表，逐条校验 `x.*` 正则后 yield 为 Fragment。  
3. core **不得**出现 `demo_tools` 等业务名；域名只存在于域包写入的 `type` 字符串里。  

**不采用：** 在 core 写死 `if name == "demo_tools"`；不采用域直接持有 `EventSink`（破坏分层）。

一期若实现成本过高，允许等价替代：**极薄 port** `ExtensionSink` 由 lifecycle 注入、域节点调用——仍禁止 core 含域名。计划阶段二选一，默认状态约定。

---

## 4. `demo_tools` 域

### 4.1 布局

```text
apps/api/domains/demo_tools/
  state.py       # 含 outbound_extensions 字段（或与约定一致）
  tools.py       # ≥1 真实 @tool，图内真正绑定
  graph.py       # 无 ChatModel / 无外部 API key
  bootstrap.py
  README.md      # 与 echo 差异、无 LLM 说明、复制指引
```

### 4.2 图约束（写死）

- **禁止**依赖 LLM / `LLM_API_KEY` 才能跑通 smoke。  
- 使用 ToolNode 或显式 tool 调用节点，保证稳定发出 `tool_call` + `tool_result`。  
- 结束前往 `outbound_extensions` 追加至少一条 `x.demo_tools.finished`（或同类合法 type）。  
- `step_update` / `text_delta`：**不强制**。

### 4.3 挂载与门禁

- `domains/bootstrap.register_all` 注册 `echo` + `demo_tools`。  
- 扫描：`packages/core` 全文不得出现 `demo_tools`；不得再引入业务节点名硬编码。

### 4.4 Web（一期软要求）

- 默认 route 可为 `echo`；文档与 Contracts 页说明 `demo_tools` 与 `x.*` 规则。  
- 推荐：调试台 route 下拉；未知 `x.*` 折叠展示（软要求，不进硬验收红线）。

---

## 5. 组装根与宿主收敛

| 项 | 设计（已拍板） |
|----|----------------|
| Fake runtime | 迁出 `lifespan.py`（如 `apps/api/testing/fake_runtime.py`）；仅 `AGENT_BASE_FAKE_RUNTIME=1` 时 import |
| 未知 route | **`RunLifecycle` / graphs.get 抛 `UnknownRoute`**；`routes/chat` **只做 HTTP 映射**（400），不长期直接摸 `app.state.graphs` 做预检（可删除预检或改为调 public 辅助，但异常源在应用层） |
| `app.state` 白名单 | **允许：** `run_lifecycle`、`settings`。**测试可暂留：** `graphs`/`tools` 仅用于 fixture 注册 double（计划中逐步改为 lifespan 测试钩子）。**禁止测试主路径：** `locks` / `cancels` 手工抢锁（改用慢 runtime + 并发请求） |
| hooks | `settings.hooks_backend=noop\|logging` |
| Postgres DSN | `settings.postgres_dsn`；工厂只收字符串 |
| 原则 | 唯一 `new` 适配器处 = lifespan；`public` 不 new |

---

## 6. 二期生产能力（概要，不阻塞一期计划）

| 能力 | 要点 |
|------|------|
| 分布式锁/cancel | ports 不变；Redis（优先）适配器；`lock_backend=inprocess\|redis` |
| 探针 | `/health` = liveness；`/ready` = checkpointer（及可选 Redis） |
| 可观测 | 可配置 LoggingHooks；可选入站 `trace_id`；JWKS TTL |
| 文档 | 未换分布式锁前不得水平扩展聊天入口 |

---

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| `x.*` 前端噪音 | 调试台折叠（软）；稳定九类优先渲染 |
| LangGraph 版本差异 | contracts 字段级映射测试 |
| `app.state` 收敛破坏测试 | 一期同步改夹具；CI 分目录跑测 |
| 误读「零改 core」 | §1.1 写死；PR 描述引用本节 |
| 扩展通道实现分叉 | §3.5 默认状态约定；计划开篇锁定一种 |

---

## 8. 验收清单

### 一期

- [ ] `contracts.md` 与 `build_event`：稳定九类 + `x.*` 一致（无「无条件透传」旧表述）  
- [ ] OutboundFragment + lifecycle 唯一编号  
- [ ] runtime：`tool_call` / `tool_result`；`step_update` 可选  
- [ ] 扩展通道通用；core 无 `demo_tools`  
- [ ] `demo_tools` 进仓、无 LLM、流验收通过  
- [ ] lifespan 无 Fake 类；`app.state` 按白名单收敛  
- [ ] echo / 409 / cancel / auth 回归绿  
- [ ] import-linter + 扫描绿  

### 二期

- [ ] 分布式锁下跨进程 409 / cancel 可测  
- [ ] `/ready` + 多副本前提文档  
- [ ] JWKS TTL；hooks/settings 可切换  

---

## 9. 与主设计关系

- 不修改 ADR-1～10 的方向；补齐实现缺口。  
- P7 多副本锁等归入本规格**二期**。  
- 下一步：`docs/superpowers/plans/2026-07-24-template-hardening-optimization-implementation.md`。

---

## 10. 决策与审阅修订记录

### 10.1 头脑风暴决策

| 问题 | 选择 |
|------|------|
| 优化节奏 | D：先模板硬化，再生产能力 |
| 一期通过线 | D：假域+工具 SSE+契约单源+组装根瘦身；不做 Redis 锁 |
| 扩展事件 | B：稳定集 + `x.<domain>.*` |
| 第二域落仓 | A：长期示例域 `demo_tools` |
| 实施路径 | 契约先行竖切 |

### 10.2 方案审阅后修订（2026-07-24）

| 项 | 修订 |
|----|------|
| 「零改 core」 | 区分本期改 core vs 硬化后新域零改 core |
| `x.*` 来源 | 写死状态约定 `outbound_extensions` + runtime 通用抽取 |
| Fragment | 增加 OutboundFragment；mapper 不再权威编号 |
| `demo_tools` | 强制无 LLM |
| 未知 route | 应用层抛错，路由只映射 |
| `app.state` | 白名单写死 |
| `step_update` | 验收不强制 |
