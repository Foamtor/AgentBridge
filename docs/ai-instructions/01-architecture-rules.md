# 架构规则

1. `application` → ports / registry / protocol；禁止 import adapters
2. adapters 只在 `apps/api/lifespan.py` 构造
3. `packages/core` 不得出现业务域名
4. 域不持有 `EventSink`；出站经 lifecycle / SSE
5. 分层由 import-linter 与 `scripts/import_scan_core.py` 守护

详见 `docs/architecture.md`。
