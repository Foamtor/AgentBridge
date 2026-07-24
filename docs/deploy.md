# Deploy

## Local (memory checkpointer)

```bash
pip install -e "packages/core[dev]" -e "apps/api[dev]"
cp .env.example .env
# USE_MEMORY_CHECKPOINTER=true
cd apps/api && uvicorn main:app --reload --port 8000
```

Web:

```bash
cd apps/web && npm install && npm run dev
```

Or from repo root: `./start-dev.sh` / `.\start-dev.ps1`.

## Postgres checkpointer

```bash
docker compose up -d postgres
# wait healthy
# .env: USE_MEMORY_CHECKPOINTER=false
pip install -e "packages/core[postgres]"
```

## Authentik（可选）

见 `infra/authentik/README.md`。`docker compose --profile auth up -d`。本地 smoke **不要求**。

`AUTH_REQUIRED=true` 时必须配置其一：

- `OIDC_ISSUER`（JWKS 验签），或
- `OIDC_JWT_SECRET`（HS256），或
- 仅本地：`AUTH_DEV_STUB=1`（任意非空 Bearer；**禁止生产**）
