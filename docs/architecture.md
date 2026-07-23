# Architecture（摘要）

- `packages/core`：编排内核（application / ports / adapters / registry / protocol）
- `apps/api`：FastAPI 宿主；`lifespan.py` 是唯一组装根；业务在 `domains/*`
- `apps/web`：React 调试台，消费稳定 SSE
- 依赖方向：application → ports/registry/protocol；adapters 只在 lifespan `new`
- 契约真源：`docs/contracts.md`

细节见：

- [主设计](superpowers/specs/2026-07-23-agent-ai-base-design.md)
- [OO 分层](superpowers/specs/2026-07-23-backend-oop-architecture.md)
- [目录结构](superpowers/specs/2026-07-23-code-structure.md)
