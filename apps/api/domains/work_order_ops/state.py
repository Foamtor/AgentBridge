from __future__ import annotations

import operator
from typing import Annotated, NotRequired, TypedDict

from langgraph.graph.message import add_messages


class WorkOrderOpsState(TypedDict):
    messages: Annotated[list, add_messages]
    outbound_extensions: NotRequired[Annotated[list, operator.add]]
