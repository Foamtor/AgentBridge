# demo_tools

无 LLM 样板域：用 Fake `AIMessage.tool_calls` + `ToolNode` 稳定打出 `tool_call` / `tool_result`，并在 State 写入 `OUTBOUND_EXTENSIONS_KEY`（`x.demo_tools.finished`）。

- 不依赖 `LLM_API_KEY` / ChatModel
- 扩展事件只写 State，不持有 `EventSink`
