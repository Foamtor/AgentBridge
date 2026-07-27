# 怎么加一个业务插件

新业务场景只加一个插件目录，尽量不要改 `packages/core`。

产品约定见 [00-AgentBridge完整方案.md](./00-AgentBridge完整方案.md)。历史材料在 `docs/superpowers/`（冲突时以完整方案为准）。

## 「业务插件」是什么

就是 `apps/api/domains/<名字>/` 下面那一套代码：对话状态、流程图、工具。  
请求里的 `route` 填这个名字，平台就知道走哪套逻辑。

（文件夹仍叫 `domains`，只是历史目录名；阅读时把它想成「业务插件」即可。）

## 步骤

1. 复制 `apps/api/domains/_scaffold` 为 `apps/api/domains/<名字>/`（或参照 `echo` / `demo_tools`）
2. 改 `state.py`（状态结构）、`tools.py`、`graph.py`（`build_<名字>_graph`）
3. 在该目录的 `bootstrap.py` 里注册：tools / graphs / input_builders
4. 在 `apps/api/domains/bootstrap.py` 的 `register_all` 里调用上面的 `register`
5. 重启 API，用调试台或 `POST /chat/stream`，`route` 填你的名字做验证

可参考的示例：

- `echo` — 最小流程，没有工具
- `demo_tools` — 无真实大模型；演示工具调用和扩展事件 `x.demo_tools.*`
- `demo_rag` — 演示检索与引用事件 `x.bridge.citation`

## 扩展事件怎么发

1. **推荐：** 把事件列表写在图状态的 `OUTBOUND_EXTENSIONS_KEY` 里（来自 `agentbridge_core.protocol.fragments`）。类型必须是合法的 `x.<业务名>.*`。运行时会在跑完后读出并推给客户端。
2. **不要：** 在业务插件里直接推 SSE，或拿着底层事件发送对象乱发。

## 运行钩子

默认 `HOOKS_BACKEND=noop`。需要日志钩子时设 `HOOKS_BACKEND=logging`。

## 什么时候才必须改核心库？

```text
新需求只影响某个业务的流程 / 工具 / 状态？
  └─ 是 → 只改 domains/<名字> 并注册。结束。

需要新增「对外固定事件类型」（不是 x.* 这种扩展）？
  └─ 是 → 改 contracts.md 和协议代码，这是接口变更，要评审。

需要改「LangGraph 某种内部信号 → 对外事件」的映射？
  └─ 是 → 改适配层（event_mapper / langgraph_runtime）。

需要改锁、取消、事件编号、结束保证？
  └─ 是 → 改 application/run_lifecycle（或换 Redis 锁等适配器）。

只是换数据库、钩子、登录配置？
  └─ 是 → 改 apps/api 的启动组装 / settings / .env，不要改核心业务逻辑。
```

## 约束

- 不同业务插件之间默认不要互相 import
- 核心库的 `application` 不能 import 业务代码；核心源码里不能写死业务名（例如 `demo_tools`）
- 图自己的 recursion_limit 等配置写在业务的 `graph.py`，不要塞进 HTTP 路由层
