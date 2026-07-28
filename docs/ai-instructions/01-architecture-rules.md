# 架构规则与反模式

入口硬规则见 [`AGENTS.md`](../../AGENTS.md)。本文只**解释** AGENTS，不另立禁令。

## 几个词（先混脸熟）

| 词 | 白话 |
|----|------|
| `application` | 包 `agentbridge_core.application`：管「一次对话怎么跑完」，**不是** `domains/` |
| Port | 接口约定（检索/数据库该长什么样） |
| adapter | Port 的具体实现；代码可在 `packages/core/.../adapters` 或 `apps/api/adapters` |
| `lifespan.py` | 组装根：在这儿**创建并注入** adapter、注册 domain |
| `EventSink` | 往外推 SSE 的口子；**domain 不要握着乱推**（路由/生命周期可以组装） |
| domain | `apps/api/domains/<名字>/` 业务插件 |

## MUST 对照（后果）

| # | 规则（摘要） | 违反会怎样 |
|---|--------------|------------|
| 1 | `application` 不直接 import `adapters` | 流程绑死实现，换后端改流程 |
| 2 | `domains/` 不持有、不乱推 `EventSink` | 事件漏号 / 未落库就推送 |
| 3 | `packages/core` 不写死业务插件名 | 核心无法复用；扫描会拦 |
| 4 | 只在组装根创建并接到应用（测例可注入） | 测试难注入；配置散落 |
| 5 | 调用方够不着的工具不进 LLM 列表；**调用再鉴权** | 模型可能乱调工具 |

分层看守：`import-linter`（主要盯 `application → adapters`）+ `scripts/import_scan_core.py`。  
domain 不 import 适配器实现：靠约定 + 代码审；见下方反模式。

## 组装根（lifespan）— 逻辑边界

**允许：**

- 在 `lifespan.py`（及其调用的 `apps/api/adapters` 工厂）里 `new` / `build_*` 适配器  
- 把实例放进 `app.state`，再交给 lifecycle / 经 metadata 注入给运行中的图  

**不允许：**

- 在 `agentbridge_core.application` 里 import 并创建适配器  
- 在 `domains/*/graph.py`（或 tools）里 `from agentbridge_core.adapters...` 或 `from adapters.postgres...` 自己创建  

业务要用检索：用已注入对象（常见 `ctx.metadata["retriever"]`），不要再 new 一套客户端。

## 依赖方向（别读成「application 去 import adapters」）

```text
routes / lifespan
  → 创建 adapters，注入 ports 的实现
  → 调用 application（生命周期）
application 只依赖 ports（接口），不依赖 adapters 包
domains 挂在注册表，由 route 选中；经注入用 Port，不 new 适配器
```

细节：[architecture.md](../architecture.md)。事件形状：[contracts.md](../contracts.md)。

## 反模式

| 反模式 | 正确做法 |
|--------|----------|
| domain 里 `from agentbridge_core.adapters... import ...` | 用 Port / `ctx.metadata` 已注入对象 |
| domain 里 `from adapters.postgres_data_source import ...` 并创建 | 同上；Postgres 只在 lifespan 接线 |
| 看见 `apps/api/adapters/` 就在 domain 里直接调用工厂 | 工厂留给 lifespan |
| `packages/core` 出现客户插件名字符串 | 名字只在 `apps/api/domains/` |
| domain 里 `sink.emit(...)` | 扩展事件进 `OUTBOUND_EXTENSIONS_KEY`（`agentbridge_core.protocol.fragments`） |
| 把「当前角色没有权限」的工具仍塞进 LLM tools | 先过滤再给模型 |
| 误以为「路由里用 SseEventSink」也违规 | 违规的是 **domain**；路由组装合法 |

## 相关

- 加插件：[02-domain-development.md](./02-domain-development.md)  
- 人类白话：[guide/03-concepts.md](../guide/03-concepts.md)
