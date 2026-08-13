# AgentBridge — Vibe Coding 接入指南

> 本文件给 AI 编程助手读的。你在帮用户把他的业务系统接入 AgentBridge。
>
> **你是谁**：读到本文件的编程助手（Cursor / Codex / Claude Code / 其他）。你要帮用户写一个 AgentBridge 业务插件，让他的业务系统具备 Agent 能力。
>
> **前提**：用户已经 clone 了 AgentBridge 仓库，你正在仓库根目录下工作。

---

## 第一步：搞清楚用户有什么

在写任何代码之前，先问用户三个问题（如果用户没主动说）：

1. **你的系统是做什么的？**（一句话，比如"政务审批系统"、"设备运维平台"、"客户工单管理"）
2. **你的系统有哪些接口或数据库？**（列出 API 端点，或者数据库表名和关键字段）
3. **用户会怎么用？**（举几个实际例子，比如"查一下本月超期未处理的工单"、"帮我生成一份设备巡检报告"）

如果用户说不清楚，让他先去看 `apps/api/domains/work_order_ops/` 的完整实现——这是一个工单系统的接入范例，看完就知道该提供什么信息。

---

## 第二步：读规矩

**你必须先读这些文件，再动手写代码。** 不读就写，大概率违反架构规则。

按顺序读：

| 顺序 | 文件 | 读完你会知道 |
|------|------|-------------|
| 1 | `AGENTS.md` | 五条不能违反的规则（MUST） |
| 2 | `docs/ai-instructions/00-project-overview.md` | 整体结构、目录地图 |
| 3 | `docs/ai-instructions/01-architecture-rules.md` | 分层规则、反模式 |
| 4 | `docs/ai-instructions/02-domain-development.md` | 怎么写插件的完整清单 |
| 5 | `docs/add-a-domain.md` | 更详细的步骤和决策树 |

**五条 MUST（从 AGENTS.md 摘录，写代码前默念一遍）：**

1. 平台流程层（`application`）不能直接 import 适配器实现
2. 业务插件（`domains/`）不能自己拿着事件发送口乱推消息
3. 核心库（`packages/core`）不能写死任何业务插件的名字
4. 适配器的创建和接线只放在 `apps/api/lifespan.py`
5. 用户没权限的工具不能出现在 LLM 的工具列表里，调用时还要再校验一次

---

## 第三步：写插件

### 3.1 从模板开始

```bash
cp -r apps/api/domains/_scaffold apps/api/domains/<业务名>
```

业务名用英文小写加下划线，比如 `gov_approval`、`device_patrol`、`customer_ticket`。

### 3.2 改四个文件

| 文件 | 做什么 | 参考 |
|------|--------|------|
| `tools.py` | 定义工具（函数 + 参数描述）。每个工具对应你的一个 API 或一次数据库查询 | `work_order_ops/tools.py` |
| `state.py` | 定义对话状态结构。通常不需要大改，从模板复制 | `work_order_ops/state.py` |
| `graph.py` | 编排流程——决定调用哪些工具、按什么顺序、结果怎么组装 | `work_order_ops/graph.py` |
| `bootstrap.py` | 注册插件——把工具、流程图、元信息挂到平台上 | `work_order_ops/bootstrap.py` |

### 3.3 注册到平台

编辑 `apps/api/domains/bootstrap.py`：

```python
# 加一行 import（注意：导入根是 domains，不是 apps.api.domains）
from domains.你的业务名 import bootstrap as your_bootstrap

# 在 DOMAIN_META_MAP 里加一条
DOMAIN_META_MAP = {
    # 保留已有内容
    "你的业务名": your_bootstrap.DOMAIN_META,
}

# 在 register_all 里加一行
def register_all(graphs, tools, input_builders=None, **kwargs):
    # 保留已有注册
    your_bootstrap.register(graphs, tools, input_builders)
```

需要审批或数据源时，再显式传入依赖：

```python
your_bootstrap.register(
    graphs,
    tools,
    input_builders,
    approval_actions=kwargs.get("approval_actions"),
    data_source=kwargs.get("data_source"),
)
```

不要让 AI 直接把 `**kwargs` 传给不接受这些参数的普通插件。

### 3.4 验证

```bash
# 启动服务
cd apps/api && uvicorn main:app --reload

# 冒烟测试
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "你的测试问题", "route": "你的业务名", "thread_id": "test-1"}'
```

看到 SSE 流式返回和 `done` 事件，说明接入成功。

---

## 四种常见模式

根据用户的业务需求，选择合适的模式：

### 模式 A：只读查询

用户问问题，系统查数据，返回表格。

**场景**：查工单、查审批记录、查设备状态、统计数据

**提示词**：
```
为 <业务名> 新增一个只读查询工具。
输入是用户的自然语言查询，输出是结构化表格。

我的数据库表：<表名和关键字段>
常见查询：<举几个例子>

要求：
- 从 _scaffold 开始，不要改 packages/core
- 数据访问用 lifespan 注入的 DataSource，不要在 domain 里创建数据库连接
- 补一条 API 冒烟测试
```

**参考**：`work_order_ops/tools.py` 里的 `list_work_orders` 和 `work_order_statistics`

### 模式 B：知识库检索

用户问问题，系统从知识库找答案，标注来源。

**场景**：查规章制度、查操作手册、查 FAQ

**提示词**：
```
为 <业务名> 接入知识检索能力。

我的知识库：<描述你的知识来源——是文档、数据库、还是外部服务>
用户会问什么：<举几个例子>

要求：
- 知识检索用 lifespan 注入的 Retriever Port，不要在 domain 里 new 客户端
- 回答时标注来源
- .env 里配置 KNOWLEDGE_BACKEND
```

**参考**：`work_order_ops/tools.py` 里的 `search_work_order_knowledge`，以及 `docs/knowledge-base.md`

### 模式 C：结构化输出（图表 / 台账）

用户要数据，系统动态生成图表或台账预览。

**场景**：统计报表、趋势图、台账草稿

**提示词**：
```
为 <业务名> 输出统计图表（ECharts 配置）和/或台账预览。

参考 work_order_ops 的扩展事件模式：
- 事件类型用 x.<业务名>.*
- 通过 OUTBOUND_EXTENSIONS_KEY 写入，不要直接推 SSE
- 后端返回纯 JSON 数据（ECharts option / 台账字段），前端负责渲染
- 不要把展示逻辑写进 packages/core
```

**参考**：`work_order_ops/graph.py` 里的图表和台账事件处理

### 模式 D：需要审批的写操作

用户要创建/修改数据，系统先生成草稿，等人工确认后才执行。

**场景**：创建工单、提交审批、修改配置、批量操作

**提示词**：
```
为 <业务名> 的写操作设计审批闭环。

我的写操作：<描述要做什么，比如"创建一条工单记录">
数据结构：<要写入的字段>

要求：
- 定义版本化 payload（approval action）
- 声明 required_permissions
- 审批前给用户看预览（草稿）
- approval_id 作为幂等键——重复审批不会创建第二条记录
- 批准后返回结构化结果（OutboundFragment）
- domain 不直接推 SSE，adapter 由 lifespan 组装
- 补测试
```

**参考**：`work_order_ops/approval.py`、`work_order_ops/tools.py` 里的 `prepare_work_order_draft`

---

## 完整提示词模板

把下面这段复制给你的 AI 编程助手：

```
你在帮我把业务系统接入 AgentBridge。按以下步骤来：

1. 先读 AGENTS.md 的五条 MUST
2. 读 docs/ai-instructions/00-project-overview.md 和 01-architecture-rules.md
3. 读 docs/ai-instructions/02-domain-development.md
4. 参考 apps/api/domains/work_order_ops/ 的完整实现

然后帮我做以下事情：

我的业务系统：<一句话描述>
我的 API / 数据库：<列出接口或表>
用户会怎么用：<举 3-5 个实际例子>

要求：
- 从 apps/api/domains/_scaffold 开始
- 不改 packages/core
- 工具权限正确设置
- 补冒烟测试
- 完成后告诉我：改了哪些文件、怎么验收
```

---

## 常见问题

### Q: 我的系统没有 REST API，只有数据库怎么办？

直接在 `tools.py` 里写数据库查询。用 lifespan 注入的 DataSource Port，不要在 domain 里自己创建数据库连接。

### Q: 我想接多个业务系统怎么办？

每个业务系统一个 `domains/<名字>/` 目录。它们共享同一套平台能力（权限、审批、审计），互不干扰。

### Q: 我的系统需要登录才能调接口怎么办？

AgentBridge 调用方的登录与权限由平台处理。业务插件通过 `RunContext` 读取已验证的用户、租户和权限信息。

如果下游业务 API 需要凭据，应在 `apps/api/lifespan.py` 或其调用的工厂中创建客户端并注入插件；不要在 domain 中读取密钥、创建认证客户端或绕过平台鉴权。

### Q: 前端怎么集成？

AgentBridge 提供标准的 SSE 接口（`POST /chat/stream`）。你的前端只需要能接收 SSE 就行。仓库里的 `apps/web` 是调试用的，不是最终前端。

### Q: 怎么接入真实的大模型？

v1.0.0 默认使用离线 FakeChatModel，保证演示和测试不依赖外部服务。仓库已有 LLM Gateway 接口和 direct/gateway 路由骨架；接入真实模型时，使用控制台模型配置或在组装根注入对应 Gateway adapter。参见 `docs/architecture.md` 和 `agentbridge_core.ports.llm_gateway`。

---

## 验收清单

插件写完后，逐项检查：

- [ ] `POST /chat/stream` + `route=<业务名>` 能返回结果
- [ ] 没有违反 AGENTS.md 的五条 MUST
- [ ] 测试通过：`pytest packages/core/tests apps/api/tests -q`
- [ ] 导入检查通过：`python scripts/import_scan_core.py`
- [ ] 知识相关测试用 `KNOWLEDGE_BACKEND=fake`

全部通过，接入完成。
