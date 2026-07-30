from __future__ import annotations

from typing import Annotated, Any, NotRequired, TypedDict

from langgraph.graph.message import add_messages


class WorkOrderOpsState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    model_alias: NotRequired[str | None]
    structured_draft: NotRequired[dict[str, Any] | None]
    current_read_call_ids: NotRequired[dict[str, str]]
    current_draft_call_id: NotRequired[str | None]
    outbound_extensions: NotRequired[list[dict[str, Any]]]
