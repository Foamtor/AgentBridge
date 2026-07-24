# 怎么开发业务插件

新业务只加 `apps/api/domains/<名字>/`，并在 `domains/bootstrap.py` 注册。

步骤见 `docs/add-a-domain.md`。  
扩展事件的 `type` 必须匹配 `x.<业务名>.*`（例如 `x.demo_tools.foo`）。
