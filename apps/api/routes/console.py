"""Safe runtime snapshot for the open-source verification workbench."""

from __future__ import annotations

from fastapi import APIRouter, Request

from auth.run_context import claims_to_run_context

router = APIRouter(prefix="/console", tags=["console"])


@router.get("/bootstrap")
async def bootstrap(request: Request) -> dict:
    settings = request.app.state.settings
    ctx = claims_to_run_context(
        getattr(request.state, "auth_claims", None),
        auth_required=settings.resolved_auth_mode != "disabled",
        policy_bundle_version=settings.policy_bundle_version,
    )
    catalog = getattr(request.app.state, "domain_catalog", [])
    reference = next((item for item in catalog if item.get("name") == "work_order_ops"), None)
    data_class = (
        "configured_source"
        if settings.enable_data_source and settings.data_source_dsn.strip()
        else "synthetic_redacted"
    )
    return {
        "release": {"version": "0.1.0", "stage": "technical_preview"},
        "runtime": {
            "auth_mode": settings.resolved_auth_mode,
            "llm_backend": settings.llm_backend,
            "llm_mode": settings.llm_mode,
            "llm_model": settings.llm_model,
            "real_model_ready": bool(
                settings.llm_mode == "openai_compatible"
                and settings.llm_api_key.strip()
            ),
            "knowledge_backend": settings.knowledge_backend,
        },
        "context": {"tenant_id": ctx.tenant_id},
        "reference": {
            "route": "work_order_ops",
            "available": reference is not None,
            "data_class": data_class,
            "capabilities": ["list", "chart", "citation", "approval_write"],
        },
    }
