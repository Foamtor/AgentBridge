from __future__ import annotations

import operator
from typing import Annotated, Any, NotRequired, TypedDict

from langgraph.graph.message import add_messages


class WorkOrderOpsState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    model_alias: NotRequired[str | None]
    structured_draft: NotRequired[dict[str, Any] | None]
    outbound_extensions: NotRequired[Annotated[list[dict[str, Any]], operator.add]]
