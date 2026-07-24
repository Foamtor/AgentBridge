# Add a domain

新业务场景只加域插件。**硬化完成后**不改 `packages/core`（一期硬化本身会改 core，见规格 §1.1）。

## 步骤

1. 复制 `apps/api/domains/_scaffold` 为 `apps/api/domains/<name>/`（或参照 `echo` / `demo_tools`）
2. 改 `state.py`（类型化 State）、`tools.py`、`graph.py`（`build_<name>_graph`）
3. 在 `bootstrap.py` 里 `tools.register` / `graphs.register` / `input_builders.register`
4. 在 `apps/api/domains/bootstrap.py` 的 `register_all` 里调用该域的 `register`
5. 重启 API，用调试台或 `POST /chat/stream` 以 `route="<name>"` 验证

样板：

- `echo` — 最小图，无 tool SSE
- `demo_tools` — 无 LLM；Fake AIMessage + ToolNode；State 写入 `OUTBOUND_EXTENSIONS_KEY` → `x.demo_tools.*`

## 扩展事件怎么发

1. **默认（推荐）：** 图 State 用 `OUTBOUND_EXTENSIONS_KEY`（来自 `agent_base_core.protocol.fragments`）存 `list[{type, data}]`；runtime 在跑完后用 `compiled.aget_state` 读取。`type` 必须合法 `x.<domain>.*`。
2. **同级高级选项：** `event_hook`（流中途推扩展；一期未实现）。简单域用 State；嵌套子图/中途推送可开 hook——二者同级，不是失败后的迫不得已。
3. **禁止：** 域持有 / 直接调用 `EventSink`。

## hooks 示例

默认 `HOOKS_BACKEND=noop`。设 `HOOKS_BACKEND=logging` 使用 `LoggingHooks`。

## 什么时候必须改 core？（决策树）

```text
新需求只影响某个业务图 / 工具 / State？
  └─ 是 → 只改 domains/<name> + bootstrap。停。

需要新的「对外 SSE 稳定类型」（不是 x.*）？
  └─ 是 → 改 contracts.md + protocol/events.py（及文档）。这是契约变更，需评审。

需要新的框架信号映射（例如某种 LangGraph 事件 → Fragment）？
  └─ 是 → 改 adapters/event_mapper.py + langgraph_runtime.py（防腐层）。

需要改锁 / cancel / 编号 / 终端保证？
  └─ 是 → 改 application/run_lifecycle.py（或二期换 Redis 适配器）。

只是换 Postgres / hooks / 鉴权配置？
  └─ 是 → 改 apps/api lifespan / settings / .env，不改 core 业务逻辑。
```

## 约束

- 域之间默认互不 import
- `application` 不得 import 域代码；core **不得**出现业务域名 / 节点名硬编码（如 `demo_tools`、`echo_node`）
- recursion_limit 等图配置写在域的 `graph.py`，不要塞进路由层
