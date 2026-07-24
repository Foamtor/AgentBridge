# Agent-Base

可复用的 AI 业务底座模板（绿场）：编排内核、OIDC 鉴权、Docker 依赖、React 调试台、域插件模型。

产品参照仓：`RAG_Agent`（继续演进业务）。本仓**对照能力重写**，不整包拷贝现网实现。

**状态：** P0–P6 主路径已落地。鉴权支持 HS256 / JWKS；本地 stub 仅 `AUTH_DEV_STUB=1`。PKCE↔Authentik 为增强项。

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
# 打开 http://127.0.0.1:5173 ，route=echo 发送

# 可选：Postgres
# docker compose up -d postgres
```

Windows 也可用仓库根目录 `.\start-dev.ps1`。

## 验证

```bash
python -m pytest packages/core/tests -v
cd apps/api && python -m pytest tests -v
lint-imports
python scripts/import_scan_core.py
```

API 已启动时：`.\scripts\smoke_echo.ps1` 或 `./scripts/smoke_echo.sh`。

## 文档

| 文档 | 用途 |
|------|------|
| [实施计划](docs/superpowers/plans/2026-07-23-agent-ai-base-implementation.md) | Task 1→13 |
| [契约](docs/contracts.md) | SSE / 鉴权 / 409 |
| [加域](docs/add-a-domain.md) | 新业务插件步骤 |
| [部署](docs/deploy.md) | 本地 / PG / Authentik |
| [与产品仓对照](docs/parity-with-product.md) | 行为对齐清单 |

## 原则

1. 双仓：产品仓做业务，本仓做底座  
2. 绿场重写：禁止大段照抄  
3. 分层 + 接口 + 构造注入 + 注册表；import-linter 锁依赖  
4. 新业务只加 `apps/api/domains/<name>`，不改内核
