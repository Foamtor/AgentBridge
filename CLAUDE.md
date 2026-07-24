# Agent-Base / AgentBridge

## 核心规则（MUST）

1. `application` 禁止 import `adapters`
2. 域代码不持有 `EventSink`
3. `core` 的 `src/` 不能出现域名称
4. 所有 adapter 只在组装根（`lifespan.py`）构造
5. 不可用的 tool 不得进入 LLM tool list

详见 `docs/ai-instructions/` 与 `docs/00-AgentBridge完整方案.md`。
