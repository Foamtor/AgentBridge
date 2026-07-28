# 全面审阅记录（2026-07-28）

> 范围：现行门面文档 + 硬规则落地 + 抽样深度文档；自动化：pytest / import-linter / import_scan / ai-instructions 存在性检查。

## 自动化结果（两轮均复跑）

| 检查 | 结果 |
|------|------|
| `pytest packages/core/tests apps/api/tests` | **209 passed, 1 skipped** |
| import-linter（5 contracts） | **全部 KEPT** |
| `scripts/import_scan_core.py` | **OK** |
| `scripts/check_ai_instructions.sh` | **ok**（Cursor Skill 改为可选） |

## 代码合规（相对 AGENTS）

| MUST | 抽查结论 |
|------|----------|
| application 不 import adapters | 通过 |
| domains 不握 EventSink | 通过 |
| core 不写死业务名 | 通过 |
| 适配器接线在 lifespan | 通过 |
| 工具权限 | `guard_tools`：list + invoke 再 `decide` |

## 第一轮已修

1. `contracts.md`：`/ingest` → 已有  
2. `knowledge-base.md`：死链与过时「无 HTTP ingest」  
3. `start-dev.sh` / `stop-dev.sh`：PID → `agentbridge-*`  
4. AGENTS/CLAUDE：测例可注入；MUST#5 双重鉴权；点名完整方案 #6/#7  
5. `guide/04`：交叉链 ai-instructions  

## 第二轮已修（修订后再审）

1. `api-reference.md`：拆分 `GET /runs` vs `/runs/{id}`；`/ingest` 与代码对齐（`knowledge:write`、已有）  
2. `contracts.md` §3.4 + 完整方案 §4.7：`/ingest` 权限改为现行 `knowledge:write`，并注明与旧 admin 表述的关系  
3. guide/03 补齐五条（含 lifespan + 调用再鉴权）；guide/04、02、add-a-domain、README/05 模板同步  
4. `knowledge-base` 标明 R-A 设计稿中「无 /ingest」已过时  
5. `check_ai_instructions.sh`：不再强制 Cursor Skill  
6. INDEX「约 5～10 分钟」；quickstart 区分「本篇通了」与 `done` 验收  

## 仍待（可接受的归档债）

| 级别 | 项 |
|------|-----|
| 低 | `docs/superpowers/` 大量历史稿仍写「无 /ingest」、死链 `design-tracks` 等——INDEX 已标归档；点进历史稿需自行辨别 |
| 低 | Windows `start-dev.ps1` 与 bash PID 文件策略不同——未在 guide 展开 |

## 门面健康度

README / guide / ai-instructions / AGENTS 主路径可用；契约与 api-reference 对 `/ingest`、`/runs` 口径已对齐代码。
