from __future__ import annotations

from typing import Any

from domains.work_order_ops.approval import make_create_work_order_handler
from domains.work_order_ops.graph import build_work_order_ops_graph
from domains.work_order_ops.tools import (
    list_work_orders,
    prepare_work_order_draft,
    search_work_order_knowledge,
    work_order_statistics,
)

DOMAIN_META = {"description": "脱敏工单运营黄金案例"}


def _build_input(
    query: str,
    *,
    model: str | None = None,
    extra: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    raw_draft = (extra or {}).get("work_order_draft")
    structured_draft = (
        dict(raw_draft)
        if isinstance(raw_draft, dict)
        else (None if raw_draft is None else {})
    )
    return {
        "messages": [{"role": "user", "content": query}],
        "model_alias": model,
        "structured_draft": structured_draft,
    }


def register(
    graphs: Any, tools: Any, input_builders: Any | None = None, **kwargs: Any
) -> None:
    tools.register(
        "work_order_ops",
        [
            list_work_orders,
            work_order_statistics,
            search_work_order_knowledge,
            prepare_work_order_draft,
        ],
    )
    graphs.register("work_order_ops", build_work_order_ops_graph)
    if input_builders is not None:
        input_builders.register("work_order_ops", _build_input)
    approval_actions = kwargs.get("approval_actions")
    data_source = kwargs.get("data_source")
    if approval_actions is not None and data_source is not None:
        approval_actions.register(
            "work_order_ops",
            "work_order_ops.create_v1",
            make_create_work_order_handler(data_source),
            {
                "name": "create_work_order",
                "required_permissions_all": ["workorder:create", "workorder:assign"],
            },
        )
