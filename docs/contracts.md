# Contracts（对外契约）

> 状态：P0 初稿（字段级样例已定；与产品仓对照见 [parity-with-product.md](./parity-with-product.md)）  
> 实现真源：本文件；`packages/core` 的 `protocol/events.py` 必须与此一致

---

## 1. HTTP 入口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | `{"status":"ok"}` |
| POST | `/chat/stream` | SSE 流式对话 |
| POST | `/chat/cancel` | 取消进行中的 run |

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
| `route` | string | 是 | 已注册图名 |
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
  "data": { "content": "hel" }
}
```

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

域扩展：`type` 可为自定义字符串；核心原样透传 `data`，不校验业务字段。

---

## 3. 鉴权

- Header：`Authorization: Bearer <access_token>`
- `AUTH_REQUIRED=false`：不校验（本地默认）
- `AUTH_REQUIRED=true`：校验 Authentik OIDC JWT（`OIDC_ISSUER` / `OIDC_AUDIENCE`）
- 未授权：`401` + `{"detail":{"code":"unauthorized"}}`

---

## 4. 核心门面（Python）

```text
orchestration_stream(lifecycle, *, query, thread_id, route, sink, ...)
cancel_run(lifecycle, *, thread_id, run_id=None)
```

- 只转发已注入的 `RunLifecycle`
- **禁止**在 `public.py` 内 `new` 任何 adapter
