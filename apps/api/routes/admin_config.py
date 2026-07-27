"""GET /admin/config — C0 read-only settings projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request

from agent_base_core.protocol.context import RunContext
from routes.admin_common import admin_ctx
from config.settings import Settings

router = APIRouter(prefix="/admin", tags=["admin"])

Tier = Literal["A", "B", "C"]


@dataclass(frozen=True)
class ConfigItemSpec:
    key: str
    field: str
    tier: Tier
    description: str


_CONFIG_MANIFEST: list[ConfigItemSpec] = [
    ConfigItemSpec("LLM_BACKEND", "llm_backend", "B", "模型路由方式"),
    ConfigItemSpec("KNOWLEDGE_BACKEND", "knowledge_backend", "B", "知识后端类型"),
    ConfigItemSpec("AUTH_REQUIRED", "auth_required", "B", "是否强制鉴权"),
    ConfigItemSpec("LOCK_BACKEND", "lock_backend", "B", "线程锁后端"),
    ConfigItemSpec("RATE_LIMIT_BACKEND", "rate_limit_backend", "B", "限流后端"),
    ConfigItemSpec("USE_MEMORY_CHECKPOINTER", "use_memory_checkpointer", "B", "内存 checkpoint"),
    ConfigItemSpec("ENABLE_DATA_SOURCE", "enable_data_source", "B", "查数 Port 开关"),
    ConfigItemSpec("HOOKS_BACKEND", "hooks_backend", "B", "Hooks 实现"),
    ConfigItemSpec("EMBED_MODEL", "embed_model", "B", "Embedding 模型名"),
    ConfigItemSpec("EMBED_API_BASE", "embed_api_base", "B", "Embedding HTTP 基址"),
    ConfigItemSpec("EMBED_DIMENSIONS", "embed_dimensions", "B", "向量维度"),
    ConfigItemSpec("POLICY_BUNDLE_VERSION", "policy_bundle_version", "B", "策略包版本"),
    ConfigItemSpec("EMBED_API_KEY", "embed_api_key", "C", "Embedding API Key"),
    ConfigItemSpec("LLM_API_KEY", "llm_api_key", "C", "LLM API Key"),
    ConfigItemSpec("OIDC_JWT_SECRET", "oidc_jwt_secret", "C", "JWT 验签密钥"),
    ConfigItemSpec("PG_PASSWORD", "pg_password", "C", "数据库密码"),
    ConfigItemSpec("DATA_SOURCE_DSN", "data_source_dsn", "C", "查数 DSN"),
    ConfigItemSpec("KB_DSN", "kb_dsn", "C", "知识库 DSN"),
]


def _require_config_read(ctx: RunContext) -> None:
    if "*" in ctx.permissions or "admin:read" in ctx.permissions:
        return
    if "admin:config" in ctx.permissions:
        return
    raise HTTPException(
        status_code=403,
        detail={"code": "forbidden", "message": "missing admin:read or admin:config"},
    )


def _is_configured(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def project_config(settings: Settings) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for spec in _CONFIG_MANIFEST:
        if spec.tier == "A":
            continue
        raw = getattr(settings, spec.field, None)
        item: dict[str, Any] = {
            "key": spec.key,
            "tier": spec.tier,
            "description": spec.description,
        }
        if spec.tier == "C":
            item["value"] = None
            item["configured"] = _is_configured(raw)
        else:
            item["value"] = raw
        items.append(item)
    return items


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    ctx = admin_ctx(request)
    _require_config_read(ctx)
    return {"items": project_config(request.app.state.settings)}
