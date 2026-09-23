"""黄金评测集测试（工单 06）：逐条运行 ``scenarios/*.json`` 并经公开 HTTP 缝断言。

每个场景 = 一次全新桩运行时 + 上下文管理 TestClient（受理 → 轮询终态 → SSE 订阅），
复用未来评测 CLI 将调用的同一对 ``run_scenario / assert_scenario``（见 harness / checks）。

运行方式（backend 目录下）：
    python -m unittest tests.evaluation.test_evaluation_suite -v

全程离线：LLM / 高德 MCP / Unsplash 均为桩实现，不触碰真实 Key 与网络。
"""

import unittest

from .checks import assert_scenario
from .harness import run_scenario
from .scenario_models import Scenario, load_scenarios

#: 黄金场景只读加载一次（文件在仓库内，不存在生成/覆盖行为）。
_GOLDEN_SCENARIOS: dict[str, Scenario] = {scenario.id: scenario for scenario in load_scenarios()}


class GoldenEvaluationTest(unittest.TestCase):
    """五条黄金样例：场景 JSON -> 公开 HTTP API 缝 -> 逐条断言。"""

    def _verify(self, scenario_id: str) -> None:
        scenario = _GOLDEN_SCENARIOS.get(scenario_id)
        if scenario is None:
            self.fail(f"缺少黄金场景 {scenario_id!r}")
        run = run_scenario(scenario)
        assert_scenario(run)

    def test_happy_path(self) -> None:
        self._verify("happy_path")

    def test_missing_date(self) -> None:
        self._verify("missing_date")

    def test_empty_search(self) -> None:
        self._verify("empty_search")

    def test_schema_retry_exhausted(self) -> None:
        self._verify("schema_retry_exhausted")

    def test_malicious_input(self) -> None:
        self._verify("malicious_input")


if __name__ == "__main__":
    unittest.main()