# 后端代码架构说明（面向对象视角）

> **阅读提示：** 这是历史设计/实施记录。文中若仍有偏内部的说法，请以仓库根目录 README、docs/roadmap.md、docs/add-a-domain.md 的白话为准。\n\n> 本文用人话讲清：后端代码**怎么拆类、怎么封装、谁实现接口、谁注入谁**。  
> 「六边形 / ports-adapters」只是业界叫法，本质就是：**面向接口编程 + 构造注入 + 分层**。  
> 主设计：[设计规格](./2026-07-23-agent-ai-base-design.md)

---

## 1. 先记住三句话

1. **路由层只收 HTTP，不写业务编排。**  
2. **编排逻辑依赖「接口」，不依赖「Postgres / LangGraph 具体类」。**  
3. **启动时把具体实现「塞进」编排类（注入）；换实现不用改编排逻辑。**

这就是以前常说的：封装、接口、依赖注入。下面展开。

---

## 2. 代码分几层（每层干一件事）

```text
┌────────────────────────────────────────────────────────────┐
│  ① 接入层（Delivery）  apps/api/routes、auth                 │
│  职责：解析请求、鉴权、调下面的服务、把结果写成 SSE/JSON     │
│  类比：Controller / API 入口                                 │
└──────────────────────────┬─────────────────────────────────┘
                           │ 只调「应用服务」
                           ▼
┌────────────────────────────────────────────────────────────┐
│  ② 应用层（Application）  agent_base_core/application       │
│  职责：一次「跑对话 / 取消」的步骤编排（加锁→建 Run→推流）   │
│  类比：Application Service / UseCase                         │
│  特点：这里写「流程」，不写 SQL，不写 JWT 细节                │
└──────────────────────────┬─────────────────────────────────┘
                           │ 只依赖「接口」（Protocol）
                           ▼
┌────────────────────────────────────────────────────────────┐
│  ③ 接口层（Ports）  agent_base_core/ports                   │
│  职责：定义抽象能力 —— 「我需要能加锁 / 存状态 / 发事件」    │
│  类比：Java Interface / C# interface / 抽象基类              │
│  特点：只有方法签名，没有具体实现                            │
└──────────────────────────┬─────────────────────────────────┘
                           │ 运行时由具体类实现
                           ▼
┌────────────────────────────────────────────────────────────┐
│  ④ 实现层（Adapters）  agent_base_core/adapters             │
│  职责：真正干活 —— 进程内锁、Postgres、LangGraph、SSE 队列  │
│  类比：Repository 实现类、基础设施类                         │
└────────────────────────────────────────────────────────────┘

另两块：
  ⑤ 注册表 Registry —— 保存「route → 建图函数 / 工具列表」（字典 + 注册方法）
  ⑥ 业务插件 Domains —— 你们自己的图和工具；启动时 register 进注册表
```

**依赖规则（硬性）：**

- ① 可以依赖 ②③④⑤⑥（接入层可为 SSE 直接用适配器，但业务流程只调 ②）  
- ② **只能**依赖 ③ 和 ⑤（以及纯数据对象），**不能** import ④ 里的具体类  
- ④ 实现 ③ 的接口  
- ⑥ 可以调用 ⑤ 的 `register_*`，**禁止**被 ②③④ import  

用人话：应用层「认识锁的概念」，「不认识」`InProcessThreadLock` 这个类名。  
注意：`GraphRuntime`、`RunCancelRegistry` 也是 **ports 里的接口**；`LangGraphRuntime` 等才是 adapters。

---

## 3. 用面向对象术语对号入座

| 老说法 | 在本项目里是什么 |
|--------|------------------|
| **封装** | `RunLifecycle` 把「加锁→跑图→推事件→解锁」包成方法；外面只调 `start_stream` / `cancel`，不碰内部步骤 |
| **接口** | `ports/` 里的 `Protocol`（或 ABC）：`ThreadLock`、`EventSink`、`CheckpointerFactory`、`RunHooks`、`GraphRuntime`、`RunCancelRegistry` |
| **实现类** | `adapters/` 里的 `InProcessThreadLock`、`SseEventSink`、`PostgresCheckpointerFactory`、`LangGraphRuntime`、`InProcessCancelRegistry` |
| **依赖注入** | 构造 `RunLifecycle` 时传入接口实现；在 `lifespan.py`（启动组装处）完成，不用满世界 `new` 具体类 |
| **多态** | 开发注入 `MemoryCheckpointer`，生产注入 `PostgresCheckpointer`，应用层代码不变 |
| **注册表 / 插件** | `GraphRegistry.register(route, builder)`；新业务不改应用层，只多注册一项 |
| **DTO / 协议对象** | `protocol/events.py` 里的事件模型（Pydantic）；进出边界用明确数据结构 |
| **防腐** | `LangGraphRuntime` 把框架内部流转换成我们的 `Event`，外面看不到 LangGraph 细节 |

「六边形」= 上面这套换了个名字，不是另一套魔法。

---

## 4. 核心类怎么设计（示意代码）

以下为**设计示意**（绿场重写时按此形状落地，不是从产品仓拷来的）。

### 4.1 接口（只定义能力）

```python
# ports/thread_lock.py
from typing import Protocol, Optional

class ThreadLock(Protocol):
    async def try_acquire(self, thread_id: str, run_id: str) -> bool:
        """拿到锁返回 True；已被占用返回 False（上层映射成 409）。"""
        ...

    async def release(self, thread_id: str, run_id: str) -> None: ...


# ports/event_sink.py
class EventSink(Protocol):
    async def emit(self, event: "OutboundEvent") -> None: ...
    async def close(self) -> None: ...


# ports/checkpointer.py
class CheckpointerFactory(Protocol):
    async def get(self): ...  # 返回 LangGraph 可用的 checkpointer


# ports/hooks.py
class RunHooks(Protocol):
    async def on_run_end(self, payload: dict) -> None: ...


# ports/graph_runtime.py
class GraphRuntime(Protocol):
    """跑已注册图；实现类里才 import langgraph。"""
    def astream(self, builder, *, tools, checkpointer, thread_id, query, cancel_token, ...):
        ...


# ports/run_control.py
class RunCancelRegistry(Protocol):
    """登记进行中的 run，供 cancel 接口协作。"""
    async def register(self, thread_id: str, run_id: str, token) -> None: ...
    async def request_cancel(self, thread_id: str, run_id: str | None) -> bool: ...
    async def unregister(self, thread_id: str, run_id: str) -> None: ...
```

### 4.2 应用服务（只编排流程，依赖接口）

```python
# application/run_lifecycle.py
class RunLifecycle:
    def __init__(
        self,
        locks: ThreadLock,                 # 注入：接口
        checkpointers: CheckpointerFactory, # 注入：接口
        graphs: GraphRegistry,             # 注入：注册表
        tools: ToolRegistry,
        runtime: GraphRuntime,             # 注入：跑图接口（非具体 LangGraph 类）
        cancels: RunCancelRegistry,        # 注入：取消登记
        hooks: RunHooks,
    ):
        self._locks = locks
        self._checkpointers = checkpointers
        self._graphs = graphs
        self._tools = tools
        self._runtime = runtime
        self._cancels = cancels
        self._hooks = hooks

    async def start_stream(self, *, query, thread_id, route, sink: EventSink, ...):
        run_id = new_id()
        if not await self._locks.try_acquire(thread_id, run_id):
            raise ThreadBusy()  # 接入层 → HTTP 409

        try:
            await sink.emit(StartEvent(run_id=run_id, ...))
            graph = self._graphs.get(route)
            toolset = self._tools.get(route)
            cp = await self._checkpointers.get()
            async for ev in self._runtime.astream(
                graph, tools=toolset, checkpointer=cp,
                thread_id=thread_id, query=query, ...
            ):
                await sink.emit(ev)
            await sink.emit(DoneEvent(...))
        except Cancelled:
            await sink.emit(CancelledEvent(...))
        finally:
            await self._hooks.on_run_end({...})
            await self._locks.release(thread_id, run_id)

    async def cancel(self, *, thread_id, run_id) -> None:
        ...
```

**封装点：** 调用方不需要知道锁怎么实现、事件怎么进 SSE；只调 `start_stream`。

### 4.3 实现类（真正干活）

```python
# adapters/inprocess_lock.py
class InProcessThreadLock:
    def __init__(self):
        self._busy: dict[str, str] = {}  # thread_id → run_id
        self._mu = asyncio.Lock()

    async def try_acquire(self, thread_id: str, run_id: str) -> bool:
        async with self._mu:
            if thread_id in self._busy:
                return False
            self._busy[thread_id] = run_id
            return True
    ...


# adapters/sse_event_sink.py
class SseEventSink:
    """把 Event 放进 asyncio.Queue，供 FastAPI StreamingResponse 读取。"""
    def __init__(self, queue: asyncio.Queue): ...
    async def emit(self, event): await self._q.put(event)


# adapters/langgraph_runtime.py
class LangGraphRuntime:
    """唯一允许大量 import langgraph 的地方之一。"""
    async def astream(self, builder, *, tools, checkpointer, thread_id, query, ...):
        graph = builder(tools=tools, checkpointer=checkpointer)
        async for chunk in graph.astream(...):
            yield map_langgraph_chunk_to_event(chunk)  # 转成我们的 Event
```

### 4.4 接入层（薄）

```python
# apps/api/routes/chat.py
@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, request: Request):
    lifecycle: RunLifecycle = request.app.state.run_lifecycle  # 启动时放好的
    queue = asyncio.Queue()
    sink = SseEventSink(queue)

    async def produce():
        try:
            await lifecycle.start_stream(
                query=body.query,
                thread_id=body.thread_id,
                route=body.route,
                sink=sink,
            )
        except ThreadBusy:
            ...  # 返回 409
        finally:
            await sink.close()

    asyncio.create_task(produce())
    return StreamingResponse(sse_from_queue(queue), media_type="text/event-stream")
```

### 4.5 启动时注入（Composition Root）

```python
# apps/api/lifespan.py
async def lifespan(app: FastAPI):
    locks = InProcessThreadLock()
    cps = PostgresCheckpointerFactory(dsn=settings.pg_dsn)
    await cps.setup()
    graphs = GraphRegistry()
    tools = ToolRegistry()

    # 业务插件自己注册，应用层不 import echo 内部细节以外的业务
    from apps.api.domains import bootstrap
    bootstrap.register_all(graphs, tools)

    runtime = LangGraphRuntime()
    cancels = InProcessCancelRegistry()
    hooks = NoopHooks()  # 或 LoggingHooks()

    app.state.run_lifecycle = RunLifecycle(
        locks=locks,
        checkpointers=cps,
        graphs=graphs,
        tools=tools,
        runtime=runtime,
        cancels=cancels,
        hooks=hooks,
    )
    yield
    await cps.teardown()
```

**这就是依赖注入：** 不是框架魔法，就是**构造函数传实现**；组装只发生在启动这一处（Composition Root），避免到处 `InProcessThreadLock()`。

---

## 5. 注册表：扩展业务时用「注册」，不用「改核心」

```python
# registry/graphs.py
class GraphRegistry:
    def __init__(self):
        self._builders: dict[str, Callable] = {}

    def register(self, route: str, builder: Callable) -> None:
        self._builders[route] = builder

    def get(self, route: str) -> Callable:
        try:
            return self._builders[route]
        except KeyError:
            raise UnknownRoute(route)


# domains/echo/bootstrap.py
def register(graphs: GraphRegistry, tools: ToolRegistry) -> None:
    tools.register("echo", [echo_tool, add_tool])
    graphs.register("echo", build_echo_graph)
```

产品仓以前的问题，用 OO 说就是：

- **没有接口边界**：编排函数直接 import 业务模块 → 耦合  
- **没有注入点**：工厂里写死 `if route == "map"` → 开闭原则被破坏（改核心才能加场景）  
- **封装泄漏**：SSE bridge 里写业务表 → 横切逻辑钻进管道  

本仓用「接口 + 注入 + 注册表」把这三处钉死。

---

## 6. 一次请求谁调用谁（时序）

```text
浏览器
  → routes.chat_stream          （接入：鉴权、开 SSE）
      → RunLifecycle.start_stream （应用：编排）
          → ThreadLock.try_acquire
          → GraphRegistry.get(route)
          → ToolRegistry.get(route)
          → CheckpointerFactory.get()
          → GraphRuntime.astream   （适配：跑 LangGraph）
              → EventSink.emit     （适配：进队列）
          → RunHooks.on_run_end
          → ThreadLock.release
      ← StreamingResponse 读队列写出 SSE
```

测试时：给 `RunLifecycle` 注入**假锁、假 sink、假 runtime**（实现同一接口的假对象），不必起 Postgres，这就是接口带来的可测性。

---

## 7. 包与类的职责一览表

| 位置 | 典型类 / 模块 | 职责 | 允许依赖 |
|------|----------------|------|----------|
| `routes/` | `chat.py` | HTTP ↔ 调用应用服务 | application、protocol |
| `auth/` | JWT 校验 | 身份 | 配置、HTTP |
| `application/` | `RunLifecycle` | 用例流程 | **仅 ports + registry + protocol** |
| `ports/` | `ThreadLock` 等 Protocol | 抽象能力 | protocol（数据类）最多 |
| `adapters/` | Lock/CP/Runtime/Sink 实现 | 基础设施 | ports、第三方库 |
| `registry/` | Graph/Tool Registry | 插件目录 | 无业务 |
| `protocol/` | Event 模型 | 边界数据结构 | 尽量纯 |
| `domains/*` | `build_*_graph`、tools | 业务图与工具 | registry、langchain、自己的代码 |
| `lifespan.py` | 组装函数 | **唯一** new 具体适配器并注入处 | 所有层 |

---

## 8. 和「以前那套 OO」的对应关系（给评审用）

| 你熟悉的说法 | 本仓落地 |
|--------------|----------|
| 面向接口编程 | `ports/*.py` 的 `Protocol` |
| 依赖倒置 | 应用层依赖抽象，实现层依赖抽象并实现之 |
| 构造注入 | `RunLifecycle(__init__(locks, ...))` |
| 单一职责 | 一层/一类只干一类事（路由不跑图，应用层不写 SQL） |
| 开闭原则 | 新业务 = 新 domain + register，不改 `RunLifecycle` |
| 里氏替换 | Memory / Postgres checkpointer 可替换 |
| 合成复用 | Runtime、Lock、Sink 组合进 Lifecycle，而不是巨型继承树 |

我们**不**搞：为每个小概念建 Entity 继承树、Repository 泛型地狱、满项目 DI 容器注解。组装用显式 `lifespan` 即可，清晰优先。

---

## 9. 小结

后端架构 = **分层（接入 / 应用 / 接口 / 实现）** + **接口定义能力** + **启动时注入实现** + **注册表挂业务**。

目录里的 `ports` / `adapters` 名字可以记成：

- **ports = 接口**  
- **adapters = 实现类**  
- **application = 用接口写流程的服务类**  
- **lifespan = 注入组装处**
