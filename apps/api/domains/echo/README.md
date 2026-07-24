# Echo domain — sample plugin

Minimal typed LangGraph: `echo_node` copies `query` → `result`.

The `echo` tool is registered for scaffolding/demo of ToolRegistry wiring.
The sample graph does **not** invoke tools yet; bind them in `graph.py` when you
want tool_call / tool_result events.
