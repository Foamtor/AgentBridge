# 与产品仓 RAG_Agent 行为对照

> 目的：本仓绿场重写时，**行为可对齐**；**实现不照抄**  
> 产品仓路径：`D:\WorkSpace\code\project\RAG_Agent`（仅作参照）

---

## 1. 能力对照

| 能力 | 产品仓位置（参照） | 本仓目标 |
|------|-------------------|----------|
| 流式入口 | `orchestration/api/stream_service.py` | `RunLifecycle` + `routes/chat.py` |
| SSE 信封 | `orchestration/sse/protocol.py` `build_sse_event` | `protocol/events.py` + `contracts.md` |
| 推流桥 | `orchestration/sse/bridge.py` | `adapters/langgraph_runtime` + `event_mapper` |
| 同 thread 锁 / 409 | `runtime/thread_lock` + stream_service | `ports.ThreadLock` + `InProcessThreadLock` |
| Cancel | `runtime/cancel_registry` | `ports.RunCancelRegistry` |
| Checkpointer | `db/checkpointer.py` | `PostgresCheckpointerFactory` / Memory |
| 图工厂写死 route | `api/graph_factory.py` | **禁止**；改 `GraphRegistry` |
| 工具按模块绑死 | `tools/registry.get_tools_for_module` | `ToolRegistry.register` |
| OIDC | Authentik + JWT 中间件 | 同协议，本仓重写 |
| 调试台 | Streamlit + 政务 React | **仅** React 调试台（重写） |

---

## 2. SSE / HTTP 差异约定

| 点 | 产品仓 | 本仓 |
|----|--------|------|
| 事件公共字段 | `type/run_id/event_id/sequence/trace_id/timestamp/data` | **对齐**（见 contracts.md） |
| `start.data` | 含 `task_type` 等 | 用 `route` + `thread_id`（不绑产品 task_type） |
| `text_delta.data` | `content` | **对齐** `content` |
| 忙冲突 | HTTP 409 | **对齐**；body 用 `thread_busy` |
| cancel 事件 | `cancel_requested` → `cancelled` | **对齐** |
| 业务扩展事件 | 地图等自定义 | 透传；本仓默认树不实现地图事件 |

允许命名微调时：必须在本表追加一行「产品字段 → 本仓字段」。

---

## 3. 明确不迁代码

- `ai_map_chat` / `app_ai_chat` / 地图 17 工具  
- Streamlit、一张图前端  
- plan_trace / 点踩表结构（仅 hooks）  
- 整目录拷贝 `orchestration/`  

新业务：在本仓 `domains/<name>` 按 scaffold **重写**图与工具。

---

## 4. 验收清单（本仓实现后勾选）

- [x] echo：`start` → … → `done` 字段符合 contracts.md  
- [x] 同 `thread_id` 二次 stream → 409 + `thread_busy`  
- [x] cancel → 流内出现 `cancel_requested` 与 `cancelled`  
- [x] `AUTH_REQUIRED=false` 可调通；`true` 无 token → 401（HS256/JWKS；stub 仅 `AUTH_DEV_STUB=1`）  
- [x] 核心 import 扫描 + import-linter 绿（CI architecture-gates）  
