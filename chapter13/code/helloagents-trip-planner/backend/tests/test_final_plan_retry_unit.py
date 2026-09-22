"""最终规划重试退避策略的单元测试（spec 第 14/47 行：指数退避）。

退避策略：3 次总尝试间延迟 0.1s（第 1→2 次）与 0.2s（第 2→3 次），即
指数退避 ``0.1 * 2^(n-1)``。sleeper 可注入，测试用记录桩验证延迟序列，
生产路径默认 ``time.sleep`` 真实等待，不经 HTTP 契约暴露。

运行方式（在 backend 目录下）：
    python -m unittest tests.test_final_plan_retry_unit -v
"""

import unittest

from app.agents.final_plan_retry import FinalPlanError, plan_final_with_retry
from app.models.schemas import TripPlan

VALID_PLAN = TripPlan(
    city="上海",
    start_date="2026-10-01",
    end_date="2026-10-03",
    days=[],
    overall_suggestions="测试行程",
)


class RecordingSleeper:
    """记录每次 sleep 的秒数，不真实等待。"""

    def __init__(self):
        self.delays: list[float] = []
        self.calls: int = 0

    def __call__(self, seconds: float) -> None:
        self.calls += 1
        self.delays.append(seconds)


class AlwaysInvalidParser:
    """对任何响应都解析失败（模拟响应不可解析为 TripPlan）。"""

    def __call__(self, response: str) -> TripPlan:
        raise ValueError(f"无法解析: {response}")


class BackoffPolicyUnitTest(unittest.TestCase):
    def test_exhausted_retries_sleep_0_1_then_0_2(self):
        """3 次尝试全部失败：退避延迟序列必须恰好为 [0.1, 0.2]（指数退避）。"""
        sleeper = RecordingSleeper()
        run_calls: list[int] = []

        def run() -> str:
            run_calls.append(len(run_calls))
            return f"response-{len(run_calls)}"

        with self.assertRaises(FinalPlanError) as ctx:
            plan_final_with_retry(run=run, parse=AlwaysInvalidParser(), sleep=sleeper)

        self.assertEqual(ctx.exception.attempts, 3)
        self.assertEqual(len(run_calls), 3, "总尝试次数必须为 3 次")
        self.assertEqual(sleeper.delays, [0.1, 0.2], "重试间退避必须指数递增 0.1s -> 0.2s")

    def test_second_attempt_success_sleeps_only_0_1(self):
        """首次失败、第二次成功：只在第 1→2 次之间退避一次 0.1s。"""
        sleeper = RecordingSleeper()
        failures = {"count": 0}

        def parse(response: str) -> TripPlan:
            if failures["count"] == 0:
                failures["count"] += 1
                raise ValueError("第一次解析失败")
            return VALID_PLAN

        result = plan_final_with_retry(run=lambda: "x", parse=parse, sleep=sleeper)

        self.assertIs(result, VALID_PLAN)
        self.assertEqual(sleeper.delays, [0.1], "仅在失败后首次重试前退避 0.1s")

    def test_no_sleep_when_first_attempt_succeeds(self):
        """首次即成功：不触发任何退避等待。"""
        sleeper = RecordingSleeper()

        result = plan_final_with_retry(
            run=lambda: "ok", parse=lambda _: VALID_PLAN, sleep=sleeper
        )

        self.assertIs(result, VALID_PLAN)
        self.assertEqual(sleeper.delays, [], "成功路径不得退避")
        self.assertEqual(sleeper.calls, 0)


if __name__ == "__main__":
    unittest.main()