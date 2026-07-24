# 测试

```bash
python -m pytest packages/core/tests -v
cd apps/api && python -m pytest tests -v
lint-imports
python scripts/import_scan_core.py
bash scripts/check_ai_instructions.sh
```

core 测试不依赖真实 LLM；API 可用 FakeRuntime。
