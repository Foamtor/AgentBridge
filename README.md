# Agent-Base

可复用的 AI 业务底座模板（绿场）：编排内核、OIDC 鉴权、Docker 依赖、React 调试台、域插件模型。

产品参照仓：`RAG_Agent`（继续演进业务）。本仓**对照能力重写**，不整包拷贝现网实现。

**状态：** 一期模板硬化已落地（契约单源、`OutboundFragment`、Option B builders、`demo_tools`、组装根瘦身）。  
**注意：模板可用 ≠ 多副本生产** — 默认进程内锁、无分布式 cancel、无完整 OTel/interrupt；水平扩展见二期（Redis 锁等）。

## 从零到绿

```bash
# 1) Python
pip install -e "packages/core[dev]" -e "apps/api[dev]"

# 2) 环境
cp .env.example .env
# 保持 USE_MEMORY_CHECKPOINTER=true（不必起 Postgres）

# 3) API
cd apps/api && uvicorn main:app --reload --port 8000

# 4) Web 调试台（另开终端）
cd apps/web && npm install && npm run dev
# 打开 http://127.0.0.1:5173
# route=echo 或 route=demo_tools（无 LLM，演示 tool_call / tool_result / x.*）
```

Windows 也可用仓库根目录 `.\start-dev.ps1`。

## 验证

```bash
python -m pytest packages/core/tests -v
cd apps/api && python -m pytest tests -v
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
```

API 已启动时：`.\scripts\smoke_echo.ps1` 或 `./scripts/smoke_echo.sh`。

## 文档

| 文档 | 用途 |
|------|------|
| [硬化规格](docs/superpowers/specs/2026-07-24-template-hardening-optimization-design.md) | 一期/二期设计 |
| [硬化实施计划](docs/superpowers/plans/2026-07-24-template-hardening-optimization-implementation.md) | Task 1→9 |
| [契约](docs/contracts.md) | 稳定九类 + `x.*` / 鉴权 / 409 |
| [加域](docs/add-a-domain.md) | 新业务插件步骤 + 何时改 core |
| [部署](docs/deploy.md) | 本地 / PG / Authentik |
| [与产品仓对照](docs/parity-with-product.md) | 行为对齐清单 |

## 原则

1. 双仓：产品仓做业务，本仓做底座  
2. 绿场重写：禁止大段照抄  
3. 分层 + 接口 + 构造注入 + 注册表；import-linter 锁依赖  
4. **硬化完成后**新业务只加 `apps/api/domains/<name>` + `bootstrap`，不改内核（一期硬化本身会改 core）  
5. 扩展事件：默认 State[`OUTBOUND_EXTENSIONS_KEY`] + `aget_state`；复杂域可用 `event_hook`（同级高级选项，一期未实现）；**域不得持有 EventSink**
