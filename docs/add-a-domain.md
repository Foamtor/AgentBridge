# Add a domain

新业务场景只加域插件，不改 `packages/core`。

## 步骤

1. 复制 `apps/api/domains/_scaffold` 为 `apps/api/domains/<name>/`
2. 改 `state.py`（类型化 State）、`tools.py`、`graph.py`（`build_<name>_graph`）
3. 在 `bootstrap.py` 里 `tools.register` / `graphs.register` / `input_builders.register`
4. 在 `apps/api/domains/bootstrap.py` 的 `register_all` 里调用该域的 `register`
5. 重启 API，用调试台或 `POST /chat/stream` 以 `route="<name>"` 验证

## hooks 示例

默认 lifespan 注入 `NoopHooks`。若要看结构化 run 结束日志，在 `apps/api/lifespan.py` 把 hooks 换成：

```python
from agent_base_core.adapters.logging_hooks import LoggingHooks
# ...
hooks=LoggingHooks(),
```

## 约束

- 域之间默认互不 import
- `application` 不得 import 域代码
- recursion_limit 等图配置写在域的 `graph.py` / scaffold 注释里，不要塞进路由层
