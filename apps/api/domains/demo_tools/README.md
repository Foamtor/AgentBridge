# demo_tools

无 LLM 样板域：用 Fake `AIMessage.tool_calls` + `ToolNode` 稳定打出 `tool_call` / `tool_result`，并在 State 写入 `OUTBOUND_EXTENSIONS_KEY`（`x.demo_tools.finished`）。

- 不依赖 `LLM_API_KEY` / ChatModel
- 扩展事件只写 State，不持有 `EventSink`
- `outbound_extensions` 使用 list append reducer，多节点可追加
- 取消为宿主协作式：停 SSE 消费，不保证立刻中断工具副作用
