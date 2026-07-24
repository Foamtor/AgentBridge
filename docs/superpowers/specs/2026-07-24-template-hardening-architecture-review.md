# Agent-Base 模板硬化设计方案 — 架构评审报告

> **阅读提示：** 这是历史设计/实施记录。文中若仍有偏内部的说法，请以仓库根目录 README、docs/roadmap.md、docs/add-a-domain.md 的白话为准。\n\n> 状态：**历史审阅归档**（实施前评审；一期代码已在 `feat/template-hardening` 落地）  
> 审阅者：资深系统架构师（ports/adapters 分层 + 构造注入 + 注册表插件架构）
> 审阅日期：2026-07-24
> 被审方案：`2026-07-24-template-hardening-optimization-design.md`
> 关联文件：主设计、代码结构、contracts.md、lifespan.py、events.py、event_mapper.py、langgraph_runtime.py、run_lifecycle.py、实施计划

---

## 总体评估

**结论：方案通过，可进入实施。** 设计在核心架构决策上方向正确，Option B 双 builder、OutboundFragment 独立模型、扩展通道状态约定是三处关键的正向设计。以下列出 7 个维度的逐项分析，区分「设计正确需坚持」「风险可控需注意」「存在架构债需改进」三档。

---

## 1. 分层纪律

### 1.1 OutboundFragment 放在 `protocol/`：正确，需坚持

**决策：** `packages/core/src/agent_base_core/protocol/fragments.py`

**评估：通过。** 这是本次方案最关键的架构锚点。

**保护了什么：**
- **依赖方向干净。** `adapters/` 和 `application/` 都依赖 `protocol/`，`OutboundFragment` 作为两者的中间契约放在 `protocol/`，不引入反向依赖。如果放在 `adapters/`，则 `application/` 需要 `import adapters`，直接违反依赖规则；如果放在 `application/`，则 `adapters/` 需反向依赖 `application/`，同样违规。
- **类型边界清晰。** `OutboundFragment` 不含 `run_id`/`sequence`/`event_id`/`timestamp`——这些是 lifecycle 层的信封字段。放在 `protocol/` 明确传达「Fragment 是语义载荷，不是完整事件」这一架构事实。
- **Pydantic `extra="forbid"`** 防止 adapters 偷偷塞信封字段，强制在 lifecycle 统一编号。

**牺牲了什么：**
- 新增一个 protocol 子模块，增加了一个 import 路径。但 `protocol/` 本就有 `events.py` / `sse.py`，增加 `fragments.py` 逻辑内聚。
- Pydantic 模型比纯 dict 有轻微性能开销。但在这个场景下（每个事件构造一次，非热路径），可忽略。

**风险：** 实施时如果 mapper 返回 Fragment 但 runtime 仍包装成 dict（带 provisional sequence），会导致 Fragment → dict → lifecycle 再解析的两阶段序列化。实施计划 Task 4-5 已明确 mapper 和 runtime 都直接产出 Fragment，方向正确。**需在 code review 时确认 runtime yield 的是 `OutboundFragment` 实例而非 dict。**

### 1.2 Option B（双 builder）对协议层的职责划分：正确

**决策：** `build_event` 仅稳定九类；`build_extension_event` 仅合法 `x.*`

**评估：通过，且优于 Option A。**

**保护了什么：**
- **语义不混淆。** 稳定九类和扩展事件虽然共用信封格式，但语义完全不同：稳定事件是契约承诺（SSE 客户端可硬解析），扩展事件是域特定（调试台折叠显示）。分函数强制调用方做出选择，避免把 `x.demo.finished` 误传给 `build_event`。
- **校验边界明确。** `build_event` 看 `EVENT_TYPES` 白名单，`build_extension_event` 看正则。两者失败都抛 `ValueError`（不是 silent drop）。这与方案 §3.6「禁止 silent drop」一致。
- **未来演进安全。** 如果稳定集从九类扩展到十类，只需改 `EVENT_TYPES`；扩展正则独立演进。

**牺牲了什么：**
- lifecycle 多一个 `if frag.type in EVENT_TYPES` 分支。但这是显式的、可测的分支，不是隐式耦合。

**实施计划中的微小不一致：** 实施计划 Task 6 说「若像扩展 → `build_extension_event`；否则 `ValueError`/`error` 路径」。这里的「像扩展」指什么？建议明确为 `EXTENSION_TYPE_RE.fullmatch(frag.type)`，否则语义模糊。

### 1.3 状态约定扩展通道（`outbound_extensions`）是否破坏分层：不破坏，有约束

**决策：** graph State 含 `outbound_extensions: list[{type, data}]`；runtime 读出 yield Fragment；lifecycle 用 `build_extension_event` 校验。

**评估：通过，但有隐式假设。**

**保护了什么：**
- **业务插件不要持有 EventSink。** 这是硬约束（§3.6「禁止域持有 EventSink」）。域只往自己的 State 写 list，不知道外面怎么消费。这个约束比 callback 方案更安全。
- **单推流路径。** 没有第二套「callback 直推 SSE」的通道，所有事件经 runtime → lifecycle → sink 一条链路。

**牺牲了什么：**
- **域必须知道 `outbound_extensions` 字段名。** 虽然这是 State 约定而非 core import，但业务插件代码中会出现字面量 `"outbound_extensions"`，这构成一个隐式协议。如果未来改名为 `"x_events"` 或换用 TypedDict 的 key，所有域都要改。
- **隐式依赖 LangGraph State 机制。** 如果未来换用非 LangGraph 运行时（如直接调 LLM SDK），`outbound_extensions` 的抽取逻辑需要在新 runtime 中重新实现。

**建议：** 在 `protocol/` 中定义一个常量 `OUTBOUND_EXTENSIONS_KEY = "outbound_extensions"`，域和 runtime 都引用此常量而非硬编码字符串。这保持了 protocol 层作为事件格式以…为准的地位，且不引入反向依赖（protocol 本就对所有层可见）。

---

## 2. 接口设计

### 2.1 Fragment → lifecycle → builder → event 链路的类型安全

**评估：存在类型间隙，但风险可控。**

**当前链路：**
```
adapters (OutboundFragment) → lifecycle (dict event) → EventSink.emit(dict)
```

**问题：** `EventSink.emit` 的签名是 `dict[str, Any]`（见 `ports/event_sink.py`），`build_event` / `build_extension_event` 返回的也是 `dict[str, Any]`。从 Fragment（强类型 Pydantic）到 event dict（无类型）之间存在类型信息丢失。

**保护了什么：** 当前设计用 `dict` 作为适配器边界的交换格式，保持了 EventSink 的简单性和可替换性（任何能收 dict 的东西都能当 sink）。

**牺牲了什么：** 如果把 `OutboundEvent` 也做成 Pydantic 模型（类似 Fragment），IDE 自动补全和类型检查能覆盖 `event["run_id"]` 这样的字段访问。当前方案在 lifecycle 内部用字符串 key 操作 dict，拼写错误只能靠测试而非类型系统发现。

**建议：** 一期可接受现有设计（改动面小）。二期可考虑 `OutboundEvent(BaseModel)` 替代 dict，EventSink 签名改为 `emit(event: OutboundEvent)`。但这不是一期硬化的阻塞项。

### 2.2 `data` 字段的 `dict[str, Any]` 是否隐藏接口泄漏

**评估：存在，但已通过 `build_event`/`build_extension_event` 的分治策略得到控制。**

**保护了什么：** `data` 用 `dict[str, Any]` 给域扩展留了灵活性，不需要为每个 `x.*` 类型定义 Pydantic 子模型。

**牺牲了什么：** lifecycle 只校验 type 字符串，不校验 data 内部结构。一个 `x.demo_tools.finished` 的 data 可以包含任意字段，SSE 客户端没有 schema 保证。

**建议：** 一期可接受。二期如果 `x.*` 事件多了，可以在 contracts.md 中为常用扩展类型约定 data schema（类似稳定九类的 JSON 样例）。方案 §4.4「Web Contracts 说明 x.*」已点出方向。

---

## 3. 防腐边界

### 3.1 LangGraph 防腐层的最小闭合是否真的"闭合"了

**评估：基本闭合，但 `on_chain_end` 的处理存在泄漏风险。**

**当前映射覆盖：**

| LangGraph 信号 | 当前状态 | 方案改进 |
|---|---|---|
| `on_chat_model_stream` → `text_delta` | ✅ 已覆盖 | 不变 |
| `on_tool_start` → `tool_call` | ✅ 已覆盖 | 不变 |
| `on_tool_end` → `tool_result` | ❌ 缺失 | ✅ 新增 |
| `on_chain_start/end` → `step_update` | ❌ 缺失 | ✅ 新增（最小） |
| `on_chain_end` → `text_delta`（fallback） | ⚠️ 存在，但有条件 | 保留 |

**问题在 `on_chain_end` 的 fallback 逻辑（`langgraph_runtime.py` L98-106）：**

```python
elif kind == "on_chain_end":
    text = _text_from_chain_output(data.get("output"))
    name = event.get("name") or ""
    if text and name and name not in {"LangGraph", "RunnableSequence"}:
        yield map_text_delta(text, ...)
```

这段代码尝试从 chain 输出中提取文本作为 `text_delta`。这是一个**补救逻辑而非防腐映射**——它在 LangGraph 内部事件和对外事件之间做了启发式转换：

**风险：**
- `_text_from_chain_output` 函数（L12-30）尝试了多种 heuristics（`output["result"]`、`messages[-1].content`、`output.content`），但没有一个正式的"这是文本输出"信号。如果 LangGraph 版本升级改变了 chain output 的结构，可能漏掉合法文本或产出错误文本。
- `name not in {"LangGraph", "RunnableSequence"}` 是硬编码黑名单，LangGraph 内部可能新增其他框架级 chain name。

**建议：** 一期保留此逻辑（它是当前 `text_delta` 的关键来源），但加一个明确的注释标注这是「启发式补救，非正式防腐映射」，并写一个针对性测试：构造一个带有特定 output 结构的假 chain event，验证产出。

### 3.2 astream_events v2 是否覆盖了所有生产需要的信号

**评估：对一期目标（demo_tools 无 LLM）够用，但对生产 LLM 场景有已知缺口。**

**已覆盖：** `on_chat_model_stream`、`on_tool_start`、`on_tool_end`、`on_chain_start`/`on_chain_end`

**已知缺口（不影响一期，但需在文档中标注）：**
- **`on_chat_model_end`**：LLM 调用完成的信号。当前方案通过 `on_chain_end` + heuristics 间接覆盖，但如果 LLM 返回 `tool_calls` 而非文本，当前逻辑可能静默丢失。
- **`on_retriever_start/end`**：如果域使用了 LangGraph 的 retriever，需要映射为检索相关事件。
- **`on_custom_event`**（LangGraph `dispatch_custom_event`）：这是最接近 `x.*` 语义的 LangGraph 原生机制，但方案选择了状态约定而非 custom event。

**建议：** 在 `docs/parity-with-product.md` 或 contracts.md 中加一节「LangGraph 防腐覆盖矩阵」，明确列出已映射和未映射的信号，标注未映射信号的替代方案或影响范围。

---

## 4. 扩展性

### 4.1 状态约定 vs callback vs port 注入的架构利弊

| 维度 | 状态约定（方案选择） | Callback（方案禁止） | Port 注入（方案降级出口） |
|---|---|---|---|
| 域是否持有 sink | ❌ 否（安全） | ✅ 是（危险） | ❌ 否（安全） |
| 推流路径数 | 1 条 | 2 条（runtime + callback） | 2 条（runtime + port） |
| 业务插件代码侵入性 | 中（需知道 `outbound_extensions` key） | 低（调 callback） | 中（调 port 方法） |
| 与 LangGraph 耦合 | 高（依赖 State 机制） | 低 | 低 |
| 扩展事件时序 | 在 graph 节点执行时写入，runtime 在流中 yield（时序可控） | 即时推（可能与 stream 事件交错） | 即时推（可能与 stream 事件交错） |

**方案选择状态约定的理由成立：**
1. 业务插件不要持有 EventSink 是硬约束（防止业务插件直接写 SSE，绕过编号和校验）
2. 单推流路径避免「第二通道」的时序混乱和调试困难
3. 与 LangGraph 的耦合在一期可接受——一期就是 LangGraph-only

**方案禁止 callback 的理由成立：** callback 本质上是「域通过 runtime 注入的函数指针」间接推事件，runtime 必须维护这个 callback 并决定何时调用。这引入了第二推流路径，且 callback 的异常处理、取消语义都需要额外设计。状态约定把这些复杂性推迟到「graph 执行完后 runtime 统一抽取」这一步，更可控。

### 4.2 降级出口设计：port 注入的触发条件是否合理

**方案 §3.6：「仅当状态约定在实现中不可行时，才允许降级为极薄 port」**

**评估：降级条件表述偏主观，建议量化。**

「不可行」没有客观标准。什么算不可行？建议改为：
- 域的扩展事件需要在 graph 执行过程中的**特定时序点**发出（而非 graph 结束后批量），且这个时序与 State 更新不同步
- 域需要发出的扩展事件数量极大（如高频率进度上报），走 State 写入会显著增加 State 体积

如果降级到 port，方案已明确两条纪律（「仍禁业务插件名、禁止业务插件持有 sink」），这是正确的。

---

## 5. 服务启动时的组装代码

### 5.1 lifespan 瘦身 + `app.state` 白名单：方案正确，但测试迁移有隐形成本

**决策：** `app.state` 生产仅暴露 `run_lifecycle` + `settings`；禁止暴露 `locks`/`cancels`/`graphs`/`tools`/`input_builders`

**评估：方向正确，是封装的基本要求。**

**保护了什么：**
- **防止交付层绕过应用层。** 如果 `app.state.graphs` 暴露，route 可能直接 `app.state.graphs.get(route)` 而不经过 `RunLifecycle`，锁、cancel、编号全部跳过。
- **防止测试依赖生产路径的私有对象。** 当前 `lifespan.py` L82-86 把所有内部对象都挂在 `app.state` 上。测试可以直接 `app.state.locks` 拿锁做断言——这在测试便利性和封装之间做了妥协。

**牺牲了什么：**
- **测试需要新的 fake 注入方式。** 当前测试可能依赖 `app.state.graphs` 注册测试图。方案把测试用的 Fake 迁到 `apps/api/testing/fake_runtime.py`，但没说测试如何注入自定义 graph 到 RunLifecycle 中。实施计划 Task 8 提到「fixture 注册方式调整」，具体方案需要在实施中明确。

**建议：** 提供 `RunLifecycle.replace_runtime()`（当前已存在，L46-48）作为测试钩子是好的起点。类似地，可以为测试提供 `RunLifecycle` 的构造期注入（通过 lifespan 的测试钩子），而非暴露内部属性。实施计划应明确至少一种测试注入 pattern。

### 5.2 adapters → adapters 同层依赖的许可：务实，但需防滥用

**决策：** 允许 `agent_base_core.adapters.* → adapters.*`（如 `langgraph_runtime → event_mapper`）；补 code-structure 一句。

**评估：有条件通过。**

**保护了什么：** 避免为简单的内部委托创建 port 抽象。`mapper` 是 `langgraph_runtime` 的内部实现细节，不值得抽象为 port。

**牺牲了什么：** 同层依赖打破了「adapters 只依赖 ports/protocol」的干净规则。如果不加约束，未来可能出现 `sse_event_sink → event_mapper`、`postgres_checkpointer → event_mapper` 等随意交叉引用。

**建议：**
1. code-structure 中补一句：「adapters 同层依赖仅限 `langgraph_runtime → event_mapper`；其他 adapters 间依赖需经 ports。」
2. import-linter 加一条规则：`adapters` 层内，除 `langgraph_runtime` 可 import `event_mapper` 外，禁止其他 adapters 间 import。可以用 import-linter 的 `forbidden` 规则实现。
3. 如果未来 `event_mapper` 被第二个 adapter 使用，考虑将其提升为 port 或提取为 `adapters/_shared/`。

---

## 6. 错误处理

### 6.1 `terminal_sent` 保证的架构完整度

**方案 §3.4：「若已 `try_acquire` 且流应对客户端有收尾，则在异常路径保证发出 `error` 或 cancel 对或 `done` 之一后再 `sink.close()`」**

**评估：语义正确，但当前 `run_lifecycle.py` 的实现存在缺口。**

**当前实现的终端事件路径：**

```
正常完成 → done（L165-172）
cancel → cancel_requested + cancelled（L144-162）
异常 → error（L127-139）
finally → sink.close()（L179）
```

**缺口分析：**

1. **`error` 路径后直接 `return`（L139），跳过了 `finally` 中的 `on_run_end`/`release`/`unregister`/`close`。** 等等——`return` 在 `try` 块内，`finally` 仍然会执行。让我重新审视：

```python
try:                    # outer try
    ...
    try:                # inner try
        async for ...
    except Exception:
        sink.emit(error)
        return          # ← 这里 return，但 finally 仍然执行
finally:
    hooks.on_run_end()
    locks.release()
    cancels.unregister()
    sink.close()
```

`return` 在 `try` 块内不影响 `finally` 执行——Python 保证 `finally` 在 `return` 前执行。所以终端事件保证是成立的：`error` 发出后，`finally` 仍会 `sink.close()`。

2. **`sink.emit` 自身失败怎么办？** 如果 `sink.emit(error)` 本身抛异常（如 SSE 连接已断），当前代码不会 catch。这个异常会传播到 `finally`，`sink.close()` 仍会执行（可能在已断连接上再次失败），`locks.release()` 也会执行。

**真正的风险：** 如果 `sink.emit(error)` 和 `sink.emit(done)` 都失败（连接彻底断开），客户端确实收不到终端事件，但这不是架构缺陷——连接已断意味着客户端不可能收到任何事件。关键问题是：**锁是否仍然释放？** 答案是肯定的（finally 保证），所以不会泄漏锁。

3. **`terminal_sent` 标志的缺失：** 方案提到 `terminal_sent` 标志，但当前 `run_lifecycle.py` 中没有这个标志。实施方案 Task 6 说「terminal_sent：acquire 成功后，保证 close 前发过 `done` 或 cancel 对或 `error` 之一」，但没有说如何实现。建议：

**建议：** 在 `start_stream` 中显式加入 `terminal_sent = False`，在发出 `done`/`error`/`cancelled` 后置 `True`，在 `finally` 中 `if not terminal_sent: await sink.emit(error(...))`。代码意图更明确，且防止未来重构时遗漏终端事件。

### 6.2 `sink.emit` 自身失败是否被考虑

**评估：未显式处理，但 finally 提供了兜底。**

当前代码中所有 `sink.emit()` 调用都没有 try/except 包裹。如果 SSE 连接在 `emit` 过程中断开：
- 异常会传播到 `except Exception` 分支（如果在内层 try 中）或直接到 `finally`
- `finally` 中的 `sink.close()` 可能再次失败
- 但 `locks.release()` 和 `cancels.unregister()` 仍然会执行

**这是可接受的行为**——连接断开时不需要向已断开的客户端发更多事件，但必须清理服务端资源。当前 finally 块的设计做到了这一点。

**建议：** 在 `finally` 块中为 `sink.close()` 加 try/except（当前可能已有，但需要验证 `SseEventSink.close` 是否 idempotent）。

---

## 7. 测试策略

### 7.1 `app.state` 收敛后，测试如何获取 fake runtime

**评估：方向正确，但实施计划中测试迁移的细节不够充分。**

**当前状态：** 测试可以通过 `app.state.graphs`、`app.state.locks` 等直接操作内部状态。收敛后这些暴露点消失。

**方案提供的替代路径：**
1. `RunLifecycle.replace_runtime()`（已存在）—— 允许测试注入 FakeRuntime
2. lifespan 测试钩子或临时 fixture（方案 §5 提到但未具体化）
3. `apps/api/testing/fake_runtime.py`（实施计划 Task 8 新建）

**缺失的部分：** 方案没有说明测试如何**注册测试用的 graph/tools**。如果 `app.state.graphs` 不再暴露，测试需要另一种方式向 RunLifecycle 注入测试域。

**建议的测试架构：**

```python
# conftest.py
@pytest.fixture
def test_lifecycle():
    """构建一个完整的 RunLifecycle，含测试 graph 注册。"""
    graphs = GraphRegistry()
    tools = ToolRegistry()
    # 注册测试 graph
    graphs.register("echo", build_echo_graph)
    ...
    return RunLifecycle(
        locks=InProcessThreadLock(),
        checkpointers=MemoryCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        runtime=FakeRuntime(),
        ...
    )
```

或者为 lifespan 提供一个 `_test_overrides` 参数（仅测试环境可用）：

```python
# lifespan.py
async def lifespan(app, _test_overrides=None):
    ...
    if _test_overrides:
        graphs = _test_overrides.get("graphs", graphs)
```

**建议：** 在实施计划 Task 8 中增加一个子步骤「明确测试注入 pattern 并写示例 fixture」。测试架构不应是实施时的「顺便解决」，而应有明确设计。

### 7.2 方案是否给出了足够的测试架构支撑

**评估：部分足够，但缺少以下关键测试场景的设计：**

| 测试场景 | 方案覆盖 | 建议 |
|---|---|---|
| Fragment 构造与校验（extra=forbid） | ✅ Task 2 | 已充分 |
| Option B builder 分派（稳定 vs 扩展） | ✅ Task 3 | 已充分 |
| `on_tool_end` 映射 | ✅ Task 4-5 | 需补充异常 tool output 的测试 |
| 扩展通道端到端（写入 State → runtime 抽取 → lifecycle 校验） | ⚠️ Task 7 集成测 | 建议加一个纯 core 层的测试（不依赖 FastAPI），验证 Fragment → event 链路 |
| terminal_sent 在各种退出路径下都发出 | ❌ 未明确 | 建议加：正常退出、cancel 退出、runtime 异常退出、sink.emit 失败退出 |
| sink.emit 失败后锁仍释放 | ❌ 未明确 | 建议加 |
| app.state 收敛后原有测试仍通过 | ⚠️ Task 8 | 需明确测试修改范围 |

---

## 总结：决策矩阵

| 维度 | 评级 | 关键建议 |
|---|---|---|
| 分层纪律 | 🟢 通过 | OutboundFragment 放 protocol 正确；Option B 正确；状态约定降级条件需量化 |
| 接口设计 | 🟢 通过 | 类型安全有间隙但一期可接受；建议定义 `OUTBOUND_EXTENSIONS_KEY` 常量 |
| 防腐边界 | 🟡 通过（有注意事项） | `on_chain_end` heuristics 需加注释和针对性测试；建议建防腐覆盖矩阵文档 |
| 扩展性 | 🟢 通过 | 状态约定选择合理；callback 禁止正确；降级 port 条件建议量化 |
| 服务启动时的组装代码 | 🟡 通过（有条件） | adapters→adapters 需 import-linter 约束；测试注入 pattern 需在实施中明确 |
| 错误处理 | 🟡 通过（有改进空间） | 建议显式 `terminal_sent` 标志；sink.emit 失败已有 finally 兜底 |
| 测试策略 | 🟡 通过（需补充） | 需明确测试注入 pattern；terminal_sent 的测试覆盖不足 |

**总体：方案可以通过并进入实施。** 三处最重要的架构决策（Fragment 在 protocol、Option B 双 builder、状态约定扩展通道）方向正确，保护了分层的核心约束。需要在实施中补强的是：错误处理的 `terminal_sent` 显式化、测试注入的 pattern 设计、以及 adapters 同层依赖的 import-linter 约束。

---

## 附录：实施前检查清单

- [ ] `protocol/` 中定义 `OUTBOUND_EXTENSIONS_KEY = "outbound_extensions"` 常量
- [ ] import-linter 加 adapters 同层依赖白名单规则
- [ ] `run_lifecycle.py` 加入显式 `terminal_sent` 标志
- [ ] 降级出口条件从「不可行」改为量化标准
- [ ] `on_chain_end` heuristics 加注释 + 针对性测试
- [ ] 测试注入 pattern 在实施计划 Task 8 中明确
- [ ] code review 确认 runtime yield 的是 `OutboundFragment` 实例而非 dict
- [ ] 确认 `sink.close()` 是 idempotent 的
- [ ] 确认 `_text_from_chain_output` 在 demo_tools 场景下的行为（demo_tools 无 LLM，不会触发 `on_chat_model_stream`，文本可能走 `on_chain_end` fallback）
