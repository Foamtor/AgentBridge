"""Safe runtime snapshot for the open-source verification workbench."""

from __future__ import annotations

from auth.run_context import claims_to_run_context
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/console", tags=["console"])


class RouteRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)

    @field_validator("query")
    @classmethod
    def query_must_contain_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must contain text")
        return value


def _route_candidates(query: str, catalog: list[dict]) -> list[dict]:
    normalized = query.casefold()
    candidates: list[dict] = []
    for domain in catalog:
        routing = domain.get("routing")
        if not isinstance(routing, dict):
            continue
        keywords = routing.get("keywords")
        if not isinstance(keywords, list):
            continue
        matched = [
            keyword for keyword in keywords
            if isinstance(keyword, str) and keyword.casefold() in normalized
        ]
        if matched:
            expected_tools: list[str] = []
            tool_rules = routing.get("tool_rules")
            if isinstance(tool_rules, list):
                for rule in tool_rules:
                    if not isinstance(rule, dict):
                        continue
                    tool = rule.get("tool")
                    rule_keywords = rule.get("keywords")
                    if (
                        isinstance(tool, str)
                        and isinstance(rule_keywords, list)
                        and any(
                            isinstance(keyword, str)
                            and keyword.casefold() in normalized
                            for keyword in rule_keywords
                        )
                    ):
                        expected_tools.append(tool)
            candidates.append(
                {
                    "route": domain.get("name"),
                    "score": len(matched),
                    "matched_keywords": matched,
                    "expected_tools": expected_tools,
                }
            )
    return sorted(candidates, key=lambda item: (-item["score"], item["route"] or ""))


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
        if settings.enable_data_source
        else "synthetic_redacted"
    )
    return {
        "release": {"version": "0.1.0", "stage": "technical_preview"},
        "runtime": {
            "auth_mode": settings.resolved_auth_mode,
            "llm_backend": settings.llm_backend,
            "llm_mode": settings.llm_mode,
            "real_model_ready": bool(
                request.app.state.model_config_service.has_real_model
            ),
            "knowledge_backend": settings.knowledge_backend,
            "observability_backend": settings.observability_store_backend,
            "checkpointer_backend": "memory" if settings.use_memory_checkpointer else "postgres",
        },
        "context": {"tenant_id": ctx.tenant_id},
        "reference": {
            "route": "work_order_ops",
            "available": reference is not None,
            "data_class": data_class,
            "capabilities": ["list", "chart", "citation", "approval_write"],
        },
    }


@router.post("/route")
async def route_query(body: RouteRequest, request: Request) -> dict:
    candidates = _route_candidates(body.query, getattr(request.app.state, "domain_catalog", []))
    if not candidates:
        return {
            "route": None,
            "reason": "No plugin routing rule matched the question.",
            "expected_tools": [],
            "candidates": [],
        }
    best = candidates[0]
    if len(candidates) > 1 and candidates[1]["score"] == best["score"]:
        return {
            "route": None,
            "reason": "More than one plugin matched the question equally.",
            "expected_tools": [],
            "candidates": candidates,
        }
    return {
        "route": best["route"],
        "reason": f"Matched keywords: {', '.join(best['matched_keywords'])}",
        "expected_tools": best["expected_tools"],
        "candidates": candidates,
    }
