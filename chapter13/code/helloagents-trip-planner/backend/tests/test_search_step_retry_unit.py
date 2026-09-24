"""搜索步骤有界重试退避策略的单元测试（spec 第 14/47 行：指数退避，仅重试失败步骤）。

与最终规划同策略：3 次总尝试间延迟 0.1s（第 1→2 次）与 0.2s（第 2→3 次），即
指数退避 ``0.1 * 2^(n-1)``。sleeper 可注入，测试用记录桩验证延迟序列与 on_retry
回调触发时机，生产路径默认 ``time.sleep`` 真实等待，不经 HTTP 契约暴露。

运行方式（在 backend 目录下）：
    python -m unittest tests.test_search_step_retry_unit -v
"""

import unittest

from app.agents.search_step_retry import SEARCH_STEP_MAX_ATTEMPTS, retry_search_step


class RecordingSleeper:
    """记录每次 sleep 的秒数，不真实等待。"""

    def __init__(self):
        self.delays: list[float] = []
        self.calls: int = 0

    def __call__(self, seconds: float) -> None:
        self.calls += 1
        self.delays.append(seconds)


def fail_attempt(error="搜索服务不可用"):
    """返回一个永远失败的 attempt：(None, [证据], validation_error)。"""
    return None, [f"搜索失败: {error}"], {"step": "attractions", "label": "景点搜索", "error": error}


class SearchStepRetryUnitTest(unittest.TestCase):
    def test_exhausted_retries_sleep_0_1_then_0_2(self):
        """3 次尝试全部失败：退避延迟序列必须恰好为 [0.1, 0.2]（指数退避）。"""
        sleeper = RecordingSleeper()
        retry_calls: list[tuple[int, float]] = []
        attempts_run: list[int] = []

        def attempt():
            attempts_run.append(len(attempts_run) + 1)
            return fail_attempt()

        result, warnings, attempts, validation = retry_search_step(
            attempt,
            sleep=sleeper,
            on_retry=lambda n, d: retry_calls.append((n, d)),
        )

        self.assertIsNone(result)
        self.assertEqual(attempts, SEARCH_STEP_MAX_ATTEMPTS)
        self.assertEqual(len(attempts_run), 3, "总尝试次数必须为 3 次")
        self.assertEqual(sleeper.delays, [0.1, 0.2], "重试间退避必须指数递增 0.1s -> 0.2s")
        # on_retry 在每次退避前触发，携带下一次尝试序号与延迟
        self.assertEqual(retry_calls, [(2, 0.1), (3, 0.2)])
        self.assertEqual(len(warnings), 3, "三次失败证据必须全部累积")
        self.assertEqual(validation, {"step": "attractions", "label": "景点搜索", "error": "搜索服务不可用"})

    def test_second_attempt_success_sleeps_only_0_1(self):
        """首次失败、第二次成功：只在第 1→2 次之间退避一次 0.1s，且返回成功结果。"""
        sleeper = RecordingSleeper()
        retry_calls: list[tuple[int, float]] = []
        count = {"n": 0}

        def attempt():
            count["n"] += 1
            if count["n"] == 1:
                return fail_attempt()
            return "ATTRACTION_RESULT", ["工具 amap_maps_text_search 执行失败: 瞬时失败"], None

        result, warnings, attempts, validation = retry_search_step(
            attempt, sleep=sleeper, on_retry=lambda n, d: retry_calls.append((n, d))
        )

        self.assertEqual(result, "ATTRACTION_RESULT")
        self.assertEqual(attempts, 2)
        self.assertEqual(sleeper.delays, [0.1], "仅在失败后首次重试前退避 0.1s")
        self.assertEqual(retry_calls, [(2, 0.1)])
        self.assertIsNone(validation, "恢复成功不携带 validation_error")
        # 首次尝试的失败证据必须保留（"先失败、重试后成功也不吞错"语义）
        self.assertEqual(len(warnings), 2, "首次失败证据 + 成功尝试证据都要保留")

    def test_no_sleep_when_first_attempt_succeeds(self):
        """首次即成功：不触发任何退避等待，attempts=1。"""
        sleeper = RecordingSleeper()

        result, warnings, attempts, validation = retry_search_step(
            lambda: ("ATTRACTION_RESULT", [], None), sleep=sleeper
        )

        self.assertEqual(result, "ATTRACTION_RESULT")
        self.assertEqual(attempts, 1)
        self.assertEqual(sleeper.delays, [], "成功路径不得退避")
        self.assertEqual(sleeper.calls, 0)
        self.assertEqual(warnings, [])

    def test_non_validation_failure_exhausts_with_none_validation(self):
        """耗尽但最后一次失败非校验类（如工具失败）：final_validation_error 为 None。"""
        sleeper = RecordingSleeper()

        def attempt():
            return None, ["景点搜索失败: 工具执行失败"], None

        result, warnings, attempts, validation = retry_search_step(attempt, sleep=sleeper)

        self.assertIsNone(result)
        self.assertEqual(attempts, SEARCH_STEP_MAX_ATTEMPTS)
        self.assertIsNone(validation, "非校验类失败不产生 validation_error 事件")
        self.assertEqual(sleeper.delays, [0.1, 0.2])

    def test_agent_exception_is_retried_and_can_recover(self):
        """Agent/外部调用抛异常时也必须重试，不能直接绕过搜索步骤重试策略。"""
        sleeper = RecordingSleeper()
        calls = 0

        def attempt():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("upstream timeout")
            return "ATTRACTION_RESULT", [], None

        result, warnings, attempts, validation = retry_search_step(attempt, sleep=sleeper)

        self.assertEqual(result, "ATTRACTION_RESULT")
        self.assertEqual(attempts, 2)
        self.assertEqual(sleeper.delays, [0.1])
        self.assertIsNone(validation)
        self.assertEqual(calls, 2)
        self.assertIn("TimeoutError: upstream timeout", warnings[0])


if __name__ == "__main__":
    unittest.main()