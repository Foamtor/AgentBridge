# 测试

```bash
python -m pytest packages/core/tests -v
cd apps/api && python -m pytest tests -v
# 仓库根目录也可以一次跑两边：
python -m pytest packages/core/tests apps/api/tests -q
lint-imports
python scripts/import_scan_core.py
bash scripts/check_ai_instructions.sh
python scripts/run_evals.py
```

核心库测试不依赖真实大模型；API 测试可用 FakeRuntime。
