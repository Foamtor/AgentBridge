# Plan 5: 协作与扩展（M8 + M9 + M10）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.  
> **Rev:** r3 — 对齐 v4.1.1；依赖矩阵：M8/M9/M10 内序；SDK 审批硬依赖 Plan4 T4。

**Goal:** M8 多 Agent 单流 + TS SDK + admin；M9 Redis 锁/限流；M10 Eval + 策略版本 + 审计导出。

## 依赖与门禁

| 方向 | 内容 |
|------|------|
| **上游硬** | Plan1 全量（`checkpoint_thread_key` + storage_key 锁语义） |
| **上游硬（条件）** | 若 SDK/金标演示审批：**Plan4 T4**；若只做 stream SDK：Plan4 可软 |
| **上游软** | Plan3（生产基线）；Plan4 M5–M7（Gateway/RAG 非 M8 必需） |
| **本 Plan 内** | T1→T2→T3→T4（**M8**）→T5→T6（**M9**）→T7→T8（**M10**）→T9 |
| **禁止** | M9 未完成时 README 写「多机生产」；Redis 锁对 storage_key **再**加 tenant 前缀 |

## Global Constraints

- 真源：v4.1.1 §4.7–4.8、M8–M10  
- 单 SSE + `data.agent_id`  
- `/admin/*` 无权限 → 403  
- Redis key：`ab:lock:{storage_key}`，`storage_key` 已含 tenant  

## Produces

| 产物 | 供谁用 |
|------|--------|
| `@agentbridge/sdk` | 前端/集成方 |
| Redis lock/limit | 多机部署 |
| Eval CI + audit export | 合规/回归 |

## Spec ↔ Task

| 规格 | Task |
|------|------|
| §4.8 agent_id | T1–T2 |
| TS SDK | T3 |
| §4.7 admin | T4 |
| M9 Redis | T5–T6 |
| M10 Eval/导出 | T7–T8 |

---

### Task 1: SSE data.agent_id

- [ ] Lifecycle/emit：若 `ctx.agent_id`，合并进 `event["data"]`  
- [ ] 契约示例更新  
- [ ] Commit `feat: SSE data.agent_id`

---

### Task 2: demo_multi_agent

- [ ] 顺序节点切换 `ctx.agent_id`（researcher → writer）  
- [ ] 一轮 stream ≥2 个 agent_id  
- [ ] Commit `feat: demo_multi_agent golden domain`

---

### Task 3: `@agentbridge/sdk`

**Interfaces:**
```typescript
export type BridgeEvent = {
  type: string;
  run_id: string;
  sequence: number;
  data?: Record<string, unknown>;
};
export class AgentBridgeClient {
  streamChat(body: unknown, handlers: { onEvent: (e: BridgeEvent) => void }): AbortController;
  resolveApproval(id: string, decision: "allow" | "deny"): Promise<void>;
}
```

- [ ] vitest parseSseChunk  
- [ ] Commit `feat(sdk): TypeScript client`

---

### Task 4: Admin API 鉴权

```python
def require_permission(ctx: RunContext, perm: str) -> None:
    if "*" in ctx.permissions or perm in ctx.permissions:
        return
    raise HTTPException(403, detail={"code": "forbidden", "message": f"missing {perm}"})
```

- [ ] `GET /admin/domains` + 403/200 测试  
- [ ] Commit `feat(api): admin domains with RBAC`

**M8 门禁：** 多 agent_id；SDK 测绿；admin 403。

---

### Task 5: RedisThreadLock

**Key：** `f"ab:lock:{storage_key}"` 其中 `storage_key=checkpoint_thread_key(tenant, thread)`（由 API 层传入，与 graph configurable.thread_id 一致）。

```python
async def try_acquire(self, thread_id: str, run_id: str) -> bool:
    # thread_id argument == storage_key
    return await redis.set(f"ab:lock:{thread_id}", run_id, nx=True, ex=self.ttl)
```

- [ ] fakeredis 或 skip 测试双 acquire  
- [ ] settings `lock_backend=memory|redis`  
- [ ] Commit `feat: redis thread lock`

---

### Task 6: Redis 限流 + multi-instance 文档

- [ ] Redis 滑动窗口（INCR+EXPIRE 或 ZSET）  
- [ ] `docs/multi-instance.md` + compose 两 api 一 redis 步骤  
- [ ] Commit `feat: redis rate limit and multi-instance doc`

**M9 门禁：** 文档步骤可复现互斥与限流（自动化能写则写）。

---

### Task 7: Eval 金标 + CI

- [ ] `evals/golden/tool_policy_viewer.json`  
- [ ] `scripts/run_evals.py` exit 1 on fail  
- [ ] CI job `evals`  
- [ ] Commit `ci: golden policy evals`

---

### Task 8: policy_bundle_version + 审计导出

- [ ] ConfigProvider 提供版本写入 RunContext  
- [ ] `GET /admin/audit/export` → JSONL（无用户原文大字段）  
- [ ] Commit `feat: policy bundle version and audit export`

---

### Task 9: 收尾

- [ ] roadmap M8–M10；README 多机仅 M9 后解锁  
- [ ] Commit `docs: Plan5 complete`

## 不在本 Plan

云 Studio、GroupChat、替代 IAM。
