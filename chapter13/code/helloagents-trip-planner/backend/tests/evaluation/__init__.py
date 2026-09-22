"""评测集基础设施（工单 06）：5 条黄金场景 + 可复用的运行/断言/真实模式支持。

组合关系：
- ``scenario_models``  场景 JSON 的信任边界解析（类型化值）
- ``stubs``            按场景配置构造新鲜桩（LLM / 高德 MCP / Unsplash）
- ``harness``          经公开 HTTP API 缝运行场景（TestClient + 依赖覆写）
- ``assert_support``   类型化 JSON 访问 + 共享 SSE / 搜索子断言
- ``checks``           逐条断言（offline 场景专属，穷尽路由）
- ``real_mode``        真实 Key 快乐路径运行器（CLI ``--real`` 专属，预检 + 结构校验）

测试与根目录 ``evaluate.py`` CLI 复用同一组 ``load_scenarios / run_scenario /
assert_scenario / run_real_happy_path`` 接口。
"""