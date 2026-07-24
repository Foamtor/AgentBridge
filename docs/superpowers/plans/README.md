# AgentBridge 实施计划索引

> 产品真源：[../../00-AgentBridge完整方案.md](../../00-AgentBridge完整方案.md) **v4.1.1**  
> 路线图：[../../roadmap.md](../../roadmap.md)  
> Plan 版本：**r3**（依赖矩阵见 [DEPENDENCIES.md](./DEPENDENCIES.md)）

按依赖顺序执行。推荐：`subagent-driven-development` 或 `executing-plans`。

| 顺序 | Plan | 文件 | 里程碑 | 版本 |
|------|------|------|--------|------|
| 1 | 可安全接入 | [2026-07-24-plan1-secure-access.md](./2026-07-24-plan1-secure-access.md) | M1+M2a+M2b | → v0.2 |
| 2 | 可查库 | [2026-07-24-plan2-datasource.md](./2026-07-24-plan2-datasource.md) | M3 | → v0.3 |
| 3 | 单机生产 | [2026-07-24-plan3-single-node-prod.md](./2026-07-24-plan3-single-node-prod.md) | M4 | → **v1.0** |
| 4 | 智能与治理 | [2026-07-24-plan4-intelligence-governance.md](./2026-07-24-plan4-intelligence-governance.md) | M5–M7 | → v1.x |
| 5 | 协作与扩展 | [2026-07-24-plan5-collaboration-scale.md](./2026-07-24-plan5-collaboration-scale.md) | M8–M10 | → 多机/v2.0 |

## 依赖一览（详情见 DEPENDENCIES.md）

```text
M0 → Plan1(M2a) → Plan2 ─┐
         ↓                │
       Plan1(M2b) ────────┼→ Plan3 → Plan4 → Plan5
         ↑ 可并行 Plan2 ──┘         │
                                    └─ SDK 审批需 Plan4·T4
```

| 消费方 | 硬前置 | 可并行/软 |
|--------|--------|-----------|
| Plan2 | Plan1 **M2a** | ∥ Plan1 M2b |
| Plan3 | Plan1 全量（至少 Pipeline） | Plan2 软 |
| Plan4 | Plan1 **含 RunStore** + Plan3 | Plan2 软 |
| Plan5 | Plan1；审批演示另需 Plan4 T4 | Plan3/4 其余软 |

**r3 相对 r2：**

- Plan1：锁与 graph 统一 `storage_key`；Produces/门禁表  
- Plan2–5：硬/软前置写死  
- 新增 DEPENDENCIES.md（矩阵 + 无环说明）  

**下一步：** Plan 1 Task 1。
