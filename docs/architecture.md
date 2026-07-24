# Architecture（摘要）

> 产品真源：[00-AgentBridge完整方案.md](./00-AgentBridge完整方案.md) **v4.1.1**。

## 当前结构（M0）

- `packages/core`：application / ports / adapters / registry / protocol
- `apps/api`：FastAPI；`lifespan.py` 组装根；`domains/*`
- `apps/web`：调试台
- 契约真源：`docs/contracts.md`

```text
HTTP → RunLifecycle → LangGraphRuntime → EventSink(SSE)
```

## 目标控制流（v4.1）

```text
Middleware → Pipeline(before) → RunLifecycle
                                    ├─ LLM Gateway（模型）
                                    ├─ Policy.decide（tool/数据）
                                    └─ append EventLog → 再 SSE emit
```

要点：

- **已提交** Event 为真源；append **先于** emit  
- Policy **按 action**（list_tools / invoke_tool / read_data / emit_text）  
- RunContext **两阶段**（先身份，创建 run 后再写 run_id）  
- Checkpointer 键：`{tenant_id}::{thread_id}`  
- 审批等待：**释放锁**；resume 同 `run_id`  
- Gateway：`LLM_BACKEND=direct|gateway` 过渡  
- OTel/metrics：执行期打点，不强制从 EventLog 投影  

里程碑见 [roadmap.md](./roadmap.md)（v1.0 = M0–M4）。

## MUST

1. application 不 import adapters  
2. 域不持有 EventSink  
3. core 无域名  
4. adapter 只在组装根构造  
5. deny 的 tool 不进 list  
6. 跨租户 Port 失败  
7. 默认 gateway 后模型必经 Gateway  

历史规格在 `docs/superpowers/`；冲突以 v4.1 为准。
