# Plan 依赖关系（r3）

> **阅读提示：** 这是历史设计/实施记录。文中若仍有偏内部的说法，请以仓库根目录 README、docs/roadmap.md、docs/add-a-domain.md 的白话为准。\n\n> 与 [README.md](./README.md)、完整方案 **v4.1.1** 附录 D 一致。  
> **硬依赖** = 未完成不可开工验收；**软依赖** = 可 Fake/跳过，功能降级。

## 总图

```text
                    M0（已有）
                       │
                       ▼
              ┌──── Plan1 ────┐
              │  T1..T7 M2a   │──────► Plan2（可与 Plan1 T8..T10 并行）
              │  T8..T10 M2b  │              │
              └───────┬───────┘              │
                      │                      │
                      ▼                      ▼
                   Plan3 ◄────────────（软：ready 探 DataSource）
                      │
                      ▼
                   Plan4（硬：Plan1 全量含 RunStore + Plan3）
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
   Plan5 M8（硬 Plan1；      Plan5 审批演示
   软 Plan3/4）              （硬 Plan4 T4）
          │
          ▼
       Plan5 M9 → M10
```

## 矩阵（行依赖列）

| ↓ 需要 \\ 提供 → | Plan1 M2a | Plan1 M2b | Plan2 | Plan3 | Plan4 T4 | Plan4 其余 |
|------------------|:---------:|:---------:|:-----:|:-----:|:--------:|:----------:|
| **Plan2** | **硬** | 软 | — | — | — | — |
| **Plan3** | **硬**（Pipeline） | 软（ready/event_log） | 软 | — | — | — |
| **Plan4** | **硬** | **硬**（RunStore） | 软 | **硬**（v1.0 纪律） | — | — |
| **Plan5 M8** | **硬** | **硬**（锁语义） | — | 软 | 条件硬* | 软 |
| **Plan5 M9** | **硬**（storage_key） | **硬** | — | 软 | — | — |
| **Plan5 M10** | **硬**（Policy/Audit） | 软 | — | 软 | — | 软 |

\*条件硬：仅当要做 SDK `resolveApproval` / 审批官方示例联调时，必须 Plan4 T4。

## 关键产物链（防漏）

| 产物 | 产出 Plan/Task | 消费 |
|------|----------------|------|
| `checkpoint_thread_key` / **storage_key 锁** | Plan1 T2+T6 | Plan4 HIL、Plan5 Redis |
| `RunStore` | Plan1 T9 | Plan4 `awaiting_approval` |
| `RequestPipeline` | Plan1 T5 | Plan2–4 插件 |
| `guard_tools` invoke 双检 | Plan1 T6 | Plan2 域、Plan5 Eval |
| `DataSource` | Plan2 | Plan3 ready、Plan4 Filter（软） |
| `/ready` `/metrics` 限流 Validator | Plan3 | v1.0、运维 |
| Approval API | Plan4 T4 | Plan5 SDK |
| Redis lock 同 storage_key | Plan5 T5 | 多机 |

## 已修正的依赖坑（r2→r3）

1. **Plan4 曾只写「Plan1」未强调 M2b** → HIL 需要 RunStore，现改为硬依赖 Plan1 全量。  
2. **锁键不一致风险** → Plan1 起 ThreadLock 即用 storage_key；Plan4/5 禁止再套 tenant 前缀。  
3. **Plan2 可并行窗口** → 明确 M2a 后验收条件即可开 Plan2，不必等 M2b。  
4. **Plan3→Plan4** → 技术上 M5 可偷跑，**发布纪律**要求先 Plan3 打完 v1.0 再称 v1.x。  
5. **Plan5 审批** → 与「仅 stream SDK」拆成条件硬依赖，避免假阻塞。

## 推荐日历序（非人天）

```text
1) Plan1 → M2a 验收条件
2) Plan1 M2b ∥ Plan2
3) Plan3 → 打 v1.0
4) Plan4（M5→M6→M7）
5) Plan5 M8 → M9 → M10
```

## 无环证明（简）

- Plan1 无上游 Plan  
- Plan2/3 只依赖 Plan1（及彼此软依赖）  
- Plan4 依赖 Plan1+3（+软 Plan2），不依赖 Plan5  
- Plan5 依赖 Plan1（+条件 Plan4），不反向依赖  

无环。
