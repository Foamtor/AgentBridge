# 域开发

新业务只加 `apps/api/domains/<name>/`，在 `domains/bootstrap.py` 注册。

步骤见 `docs/add-a-domain.md`。扩展事件 type 必须匹配 `x.<domain>.*`。
