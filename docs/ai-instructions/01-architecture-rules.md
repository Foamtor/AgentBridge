# 架构规则

1. 流程层（`application`）可以依赖接口约定 / 注册表 / 协议；禁止直接 import 适配器实现
2. 适配器只在 `apps/api/lifespan.py`（服务启动组装处）创建
3. `packages/core` 源码里不能写死某个业务插件的名字
4. 业务插件不要自己拿着 `EventSink` 推事件；出站走统一生命周期 / SSE
5. 分层由 import-linter 与 `scripts/import_scan_core.py` 检查

详见 `docs/architecture.md`。
