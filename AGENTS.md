# AgentBridge / AgentBridge

## 必须遵守

1. 流程层（`application`）禁止直接 import `adapters`
2. 业务插件代码不要自己拿着事件发送对象（`EventSink`）乱推
3. 核心库 `src/` 里不能写死某个业务插件的名字
4. 数据库、检索等具体实现，只在服务启动组装处（`lifespan.py`）创建
5. 没权限的工具不能进入模型可见的工具列表

详见 `docs/ai-instructions/` 与 `docs/00-AgentBridge完整方案.md`。
