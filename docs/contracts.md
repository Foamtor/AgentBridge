# 对外接口约定（Contracts）

> 状态：SSE / chat 约定已实现；与产品仓对照见 [parity-with-product.md](./parity-with-product.md)  
> **以本文件 + `packages/core` 的 `protocol/events.py` 为准**（两边必须一致）  
> 产品总说明：[00-AgentBridge完整方案.md](./00-AgentBridge完整方案.md)；接口列表见 [api-reference.md](./api-reference.md)

---

## 1. HTTP 入口

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/health` | `{"status":"ok"}` | 已有 |
| POST | `/chat/stream` | SSE 流式对话 | 已有 |
| POST | `/chat/cancel` | 取消进行中的 run | 已有 |
| GET | `/ready` | 依赖就绪 | 已有 |
| GET | `/threads` | 对话列表 | 已有 |
| GET | `/threads/{id}/messages` | 消息历史 | 已有 |
| GET | `/runs`、`/runs/{id}` | Run 状态 | 已有 |
| GET | `/runs/{id}/events` | 事件回放 | 已有 |
| GET | `/metrics` | Prometheus | 已有 |
| GET/POST | `/approvals/*` | 人工审批 | 已有 |
| POST | `/ingest` | 文档摄取 | 视部署是否提供 |
| GET/POST | `/admin/*` | 管理接口 | 已有（如 domains / audit export） |

### 1.1 `POST /chat/stream`

**Request JSON**

```json
{
  "query": "hello",
  "thread_id": "t-demo-001",
  "route": "echo",
  "model": "default",
  "extra": {}
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 用户输入 |
| `thread_id` | string | 是 | 会话键（锁与 checkpoint 粒度） |
| `route` | string | 是 | 已注册的业务插件名 |
| `model` | string | 否 | 模型别名，默认 `default` |
| `extra` | object | 否 | 传给 input_builder / configurable |

**成功响应**

- Status：`200`
- `Content-Type: text/event-stream`
- Body：多行 `data: {json}\n\n`（见 §2）

**同 thread 忙**

- Status：`409`
- Body：

```json
{
  "detail": {
    "code": "thread_busy",
    "thread_id": "t-demo-001",
    "message": "thread already has a running run"
  }
}
```

**未知 route**

- Status：`400`
- `code`: `unknown_route`

### 1.2 `POST /chat/cancel`

```json
{
  "thread_id": "t-demo-001",
  "run_id": "r-optional"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `thread_id` | 是 | |
| `run_id` | 否 | 省略则取消该 thread 当前 run |

成功：`200` + `{"ok": true}`；无进行中 run：`404` + `code: run_not_found`。

---

## 2. SSE 事件信封

每条 SSE 的 `data` 为一个 JSON 对象，**公共字段**：

```json
{
  "type": "start",
  "run_id": "r-abc",
  "event_id": "r-abc-1",
  "sequence": 1,
  "trace_id": "tr-xyz",
  "timestamp": 1721721600000,
  "data": {}
}
```

| 字段 | 说明 |
|------|------|
| `type` | 事件类型（下表） |
| `run_id` | 本次 Run |
| `event_id` | `{run_id}-{sequence}` |
| `sequence` | 从 1 递增 |
| `trace_id` | 可选链路 ID；无则可与 `run_id` 相同 |
| `timestamp` | 毫秒 epoch |
| `step` / `status` | 可选；`step_update` 常用 |
| `data` | 类型相关载荷 |

### 2.1 稳定类型与样例

**`start`**

```json
{
  "type": "start",
  "run_id": "r-abc",
  "event_id": "r-abc-1",
  "sequence": 1,
  "trace_id": "tr-xyz",
  "timestamp": 1721721600000,
  "data": {
    "thread_id": "t-demo-001",
    "route": "echo"
  }
}
```

**`step_update`**

```json
{
  "type": "step_update",
  "run_id": "r-abc",
  "event_id": "r-abc-2",
  "sequence": 2,
  "trace_id": "tr-xyz",
  "timestamp": 1721721600100,
  "step": "echo_node",
  "status": "running",
  "data": {}
}
```

**`text_delta`**

```json
{
  "type": "text_delta",
  "run_id": "r-abc",
  "event_id": "r-abc-3",
  "sequence": 3,
  "trace_id": "tr-xyz",
  "timestamp": 1721721600200,
  "data": { "content": "hel", "agent_id": "researcher" }
}
```

多 Agent（§4.8）：若 `RunContext.agent_id` 非空，Lifecycle 会把 `agent_id` **合并进** `data`（fragment 已带则保留）；同流可切换多个 `agent_id`。

**`tool_call`**

```json
{
  "type": "tool_call",
  "run_id": "r-abc",
  "event_id": "r-abc-4",
  "sequence": 4,
  "trace_id": "tr-xyz",
  "timestamp": 1721721600300,
  "data": {
    "name": "echo",
    "args": { "text": "hello" },
    "tool_call_id": "tc-1"
  }
}
```

**`tool_result`**

```json
{
  "type": "tool_result",
  "run_id": "r-abc",
  "event_id": "r-abc-5",
  "sequence": 5,
  "trace_id": "tr-xyz",
  "timestamp": 1721721600400,
  "data": {
    "name": "echo",
    "ok": true,
    "tool_call_id": "tc-1",
    "summary": "hello"
  }
}
```

**`done`**

```json
{
  "type": "done",
  "run_id": "r-abc",
  "event_id": "r-abc-6",
  "sequence": 6,
  "trace_id": "tr-xyz",
  "timestamp": 1721721600500,
  "data": {}
}
```

**`error`**

```json
{
  "type": "error",
  "run_id": "r-abc",
  "event_id": "r-abc-7",
  "sequence": 7,
  "trace_id": "tr-xyz",
  "timestamp": 1721721600600,
  "data": {
    "message": "tool failed",
    "code": "tool_error"
  }
}
```

**`cancel_requested`**

```json
{
  "type": "cancel_requested",
  "run_id": "r-abc",
  "event_id": "r-abc-8",
  "sequence": 8,
  "trace_id": "tr-xyz",
  "timestamp": 1721721600700,
  "data": {
    "thread_id": "t-demo-001",
    "run_id": "r-abc"
  }
}
```

**`cancelled`**

```json
{
  "type": "cancelled",
  "run_id": "r-abc",
  "event_id": "r-abc-9",
  "sequence": 9,
  "trace_id": "tr-xyz",
  "timestamp": 1721721600800,
  "data": {
    "thread_id": "t-demo-001",
    "run_id": "r-abc"
  }
}
```

### 2.2 事件类型规则

**稳定九类**（仅这些可由核心 `build_event` 构造）：

`start` · `step_update` · `text_delta` · `tool_call` · `tool_result` · `done` · `error` · `cancel_requested` · `cancelled`

**扩展集**（域自定义，经 `build_extension_event` 出站）：

- `type` 必须匹配：`^x\.[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$`  
  （业务插件名段后至少一段；**禁止**连续点 `..` 与尾部点 `.`）
- 示例：`x.demo_tools.finished`
- 非法扩展 type（如 `X.UPPER.x`、`x.`、`custom`）**不得出站**；应用层拒绝，禁止静默透传

域扩展的 `data` 业务字段由域约定；核心只校验 `type` 形态，不校验 `data` 内部 schema。

---

## 3. 鉴权

- Header：`Authorization: Bearer <access_token>`
- `AUTH_REQUIRED=false`：不校验（本地默认）
- `AUTH_REQUIRED=true`：校验 Authentik OIDC JWT（`OIDC_ISSUER` / `OIDC_AUDIENCE`）或 HS256
- 未授权：`401` + `{"detail":{"code":"unauthorized"}}`

### 3.1 JWT → RunContext（规划 M2a）

| claim | RunContext |
|-------|------------|
| `sub` | `user_id` |
| `tenant_id` 或 `tid` | `tenant_id` |
| `roles` | `roles` |
| `permissions` 或 `perms` | `permissions` |

`AUTH_REQUIRED=false` 时开发默认：`user_id=dev`、`roles=["admin"]`、`permissions=["*"]`。

**两阶段**：JWT 只填身份字段；Lifecycle 创建 `run_id` 后再写入 configurable（完整方案 §4.1）。

**Checkpointer 存储键**：`{tenant_id}::{thread_id}`（对外 API 的 `thread_id` 不变）。

### 3.2 事件权威说明与消息投影（规划 M2b）

- **EventLog** = **已成功 append** 的出站事件；为 run 权威说明  
- **顺序**：先 `append` 成功，再 SSE `emit`；append 失败则终止，不得继续推业务事件  
- **MessageStore**：终端事件已提交后的对话摘要投影  
- `text_delta` 不强制逐 token 投影；EventLog 可对 delta 采样/合并（见完整方案 §4.2）  
- **断连**：表示 run 未完整终端；已提交前缀仍可回放，不是「权威说明不可信」

### 3.3 规划中的治理类 SSE

- `x.bridge.approval_required` / `x.bridge.approval_resolved`（审批等待默认**释放** thread 锁，见完整方案 §4.6）  
- `x.bridge.citation`  
- 多 Agent：**单流**，`data.agent_id` / `parent_run_id`（§4.8）

### 3.4 管理面鉴权（规划）

`/admin/*`、写 `/prompts`、写 `/ingest` 需 admin 类 permission；`/approvals/*` 需 `approval:decide`（或配置等价物）。见完整方案 §4.7。

---

## 4. 核心门面（Python）

```text
orchestration_stream(lifecycle, *, query, thread_id, route, sink, ...)
cancel_run(lifecycle, *, thread_id, run_id=None)
```

- 只转发已注入的 `RunLifecycle`
- **禁止**在 `public.py` 内 `new` 任何 adapter
- M2a+：可经 Pipeline 入口调用；`public.py` 同时兼容 lifecycle 与 pipeline  
- M2a+：Policy 过滤 tool list（`list_tools`）+ 执行期再检（`invoke_tool`）  
- M2b+：emit 路径 **append-before-emit** 写 EventLog  
- M5+：`LLM_BACKEND=direct|gateway`（见完整方案 §5.2）
