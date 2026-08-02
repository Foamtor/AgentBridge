# 怎么开发业务插件

新业务 = 新目录 `apps/api/domains/<名字>/` + 在总表注册。  
尽量**不要**改 `packages/core`。

人类向导：[guide/04-first-plugin.md](../guide/04-first-plugin.md)  
逐步清单（细节以此为准）：[add-a-domain.md](../add-a-domain.md)

## 怎样算成功（最低）

1. `POST /chat/stream` 使用 `"route":"<名字>"` 能跑通，并出现 `done`（或调试台可选中并发一句有回复）  
2. 未违反 [`AGENTS.md`](../../AGENTS.md)  

**建议（强烈）：** 补一条 API 冒烟测试（清单第 8 步）；没有测试不算「可合并」，但本地探路可以先做到第 1～2 条。

## 检查清单（按顺序勾）

1. [ ] 读懂样板：`apps/api/domains/echo/`（最小、无模型）  
2. [ ] 复制 `apps/api/domains/_scaffold/` → `apps/api/domains/<名字>/`（需要工具示例再对照 `demo_tools`）  
3. [ ] 改该目录：`state.py` / `graph.py` / `tools.py` / `bootstrap.py`  
4. [ ] 改总表 `apps/api/domains/bootstrap.py`：`import`、`register_all` 调用、`DOMAIN_META_MAP`  
5. [ ] 工具权限：需要则挂 `required_permissions`；**当前调用方不具备的权限所对应的工具，不要进 LLM 可见列表**；调用时平台会再鉴权（勿只靠藏列表）  
6. [ ] **若**发扩展事件：从 `agentbridge_core.protocol.fragments` 使用 `OUTBOUND_EXTENSIONS_KEY`；`type` 必须是 `x.<业务名>.*`；不要手推 SSE  
7. [ ] 确认进程已加载新代码（`--reload` 下改已有文件通常会重载；新增包/注册表变更若未生效则重启）  
8. [ ] （建议）补测试，参考 `apps/api/tests/test_chat_stream.py`

### 真实业务模式参考

`work_order_ops` 不是脚手架：它用于参考“只读查询 + 列表/图表扩展事件 + citation + 审批写入”的完整模式。需要其中某项时只阅读对应文件和测试；不要复制 route 名、SQL 表名、处理人字段或 RAG-Agent 配置到新业务。

## 注册时会碰到的对象

| 对象 | 作用 |
|------|------|
| `graphs.register(名字, build_xxx_graph)` | 该 `route` 的流程图 |
| `tools.register(名字, [tool, ...])` | 该路由挂上的工具（可为空列表，视插件而定） |
| `input_builders.register(...)` | 把 `query` 等收成图的初始 state |
| `DOMAIN_META` / `DOMAIN_META_MAP` | 说明文字；调试台展示用 |

## 常见错误

| 错误 | 修好 |
|------|------|
| 只改了目录，忘了改 `apps/api/domains/bootstrap.py` | 补注册并重启；否则 `unknown route` |
| 扩展事件写成 `x.别的插件.foo` 或非 `x.` | 改成 `x.<自己的名字>.*` |
| 在 domain 里直接推 SSE / 握 `EventSink` | 改走 `OUTBOUND_EXTENSIONS_KEY` |
| 在 domain 里 `from adapters...` / `agentbridge_core.adapters...` 并创建 | 违反组装边界；改用注入的 Port |
| 把业务名写进 `packages/core` | 删掉；逻辑放 domain |
| 路径写成仓库根下的 `domains/echo` | 正确：`apps/api/domains/...` |
| editable 仍指向旧目录 | `pip install -e "packages/core[dev]" -e "apps/api[dev]"` |

## 什么时候才动核心库？

见 [add-a-domain.md](../add-a-domain.md) 决策树。一句话：  
**只影响某一业务的流程/工具/状态 → 只改 domain。**  
改稳定事件类型、生命周期、锁语义 → 要评审，别偷偷改。
