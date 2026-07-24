# demo_tools — 工具调用示例插件

不接真实大模型：用假的工具调用消息 + ToolNode，稳定打出 `tool_call` / `tool_result`，并在状态里写入扩展事件（`x.demo_tools.finished`）。

- 不需要 `LLM_API_KEY`
- 扩展事件只写在状态里，业务插件不自己推 SSE
- 取消由宿主配合：停掉消费即可，不保证立刻打断工具副作用
