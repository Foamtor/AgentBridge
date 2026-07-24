# 业务插件模板

把本目录复制到 `apps/api/domains/<你的名字>/`，再改符号名。

## 清单

1. 在 `graph.py` 里把 `build_<name>_graph` 改成你的名字  
2. 在 `state.py` 定义状态结构（可参考 `echo`）  
3. 在 `bootstrap.py` 注册工具、流程图、输入构造  
4. 在 `apps/api/domains/bootstrap.py` 里调用 `register(...)`  
5. 若流程图可能循环，在 `compile(...)` 里设置 recursion_limit  

**不要** import 其它业务插件。  
**不要** 为了新业务去改 `packages/core`（除非你在改平台级约定）。
