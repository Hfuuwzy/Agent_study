"""搜索步骤有界重试的 API 缝回归测试 + 每步 loguru 诊断验证。

场景（spec 第 28/29/47 行 + 交接工单）：
- 某一步骤瞬时失败、重试恢复：只重试失败步骤，已成功步骤不重跑；失败证据保留
  （"先失败、重试后成功也不吞错"），终态 degraded 但带真实计划。
- 某一步骤始终失败：3 次尝试耗尽 -> 显式 degraded 空壳，不伪造成功，规划不执行。
- 每步 loguru 控制台诊断：以 run_id 贯穿，记录 step / status / elapsed_ms /
  error（含 step_retrying 与 step_exhausted），不写日志文件。

测试缝 = 公开 HTTP API（POST /api/trip/plan + GET /runs/{id} + SSE），与 spec
Testing Decisions 一致；全程离线桩驱动、零新增依赖、零写盘。

运行方式（在 backend 目录下）：
    python -m unittest tests.test_search_step_retry -v
"""

import time
import unittest

from fastapi.testclient import TestClient
from loguru import logger

from app.api.main import app
from app.runtime.factory import AppRuntime, RuntimeFactory, get_app_runtime
from tests.stubs import DEFAULT_ATTRACTIONS_JSON, DEFAULT_HOTELS_JSON, StubAmapTool, StubLLM, StubUnsplash, TextSearchStub

REQUEST = {
    "city": "上海", "start_date": "2026-10-01", "end_date": "2026-10-03",
    "travel_days": 3, "transportation": "公共交通", "accommodation": "经济型酒店",
    "preferences": ["历史文化"], "free_text_input": "",
}

TERMINAL_STATUSES = ("success", "degraded", "failed")


class FlakyAttractionOnceSearch(TextSearchStub):
    """景点搜索首次调用失败、重试即成功；酒店搜索恒正常（用于验证"只重试失败步骤"）。"""

    def __init__(self, attractions_text=DEFAULT_ATTRACTIONS_JSON, hotel_text=DEFAULT_HOTELS_JSON):
        super().__init__(attractions_text, hotel_text)
        self._failures_left = 1
        self.attraction_calls = 0
        self.hotel_calls = 0

    def run(self, parameters):
        keywords = str((parameters or {}).get("keywords", ""))
        if "酒店" in keywords or "宾馆" in keywords:
            self.hotel_calls += 1
            return super().run(parameters)
        self.attraction_calls += 1
        if self._failures_left > 0:
            self._failures_left -= 1
            raise RuntimeError("景点搜索服务瞬时失败")
        return super().run(parameters)


class AttractionAlwaysFailSearch(TextSearchStub):
    """景点搜索始终失败：用于验证重试耗尽后的显式降级。"""

    def __init__(self, attractions_text=DEFAULT_ATTRACTIONS_JSON, hotel_text=DEFAULT_HOTELS_JSON):
        super().__init__(attractions_text, hotel_text)
        self.attraction_calls = 0
        self.hotel_calls = 0

    def run(self, parameters):
        keywords = str((parameters or {}).get("keywords", ""))
        if "酒店" in keywords or "宾馆" in keywords:
            self.hotel_calls += 1
            return super().run(parameters)
        self.attraction_calls += 1
        raise RuntimeError("景点搜索服务不可用")


class SearchStepRetryHttpTest(unittest.TestCase):
    def setUp(self):
        self.llm = StubLLM(city="上海", start_date="2026-10-01", end_date="2026-10-03", travel_days=3)
        self.amap = StubAmapTool()
        self.unsplash = StubUnsplash()
        self.runtime = self._runtime(lambda: self.amap)
        self.client = TestClient(app)
        self.client.__enter__()
        # 捕获以 step_ 开头的 loguru 控制台诊断（内存 sink，不写日志文件）
        self.log_records: list[str] = []
        self._log_handler = logger.add(
            self.log_records.append,
            format="{message}",
            level="INFO",
            filter=lambda record: str(record["message"]).startswith("step_"),
        )

    def tearDown(self):
        logger.remove(self._log_handler)
        self.client.__exit__(None, None, None)
        self.runtime.close()
        app.dependency_overrides.clear()

    def _runtime(self, amap_factory):
        runtime = AppRuntime(factory=RuntimeFactory(
            llm_factory=lambda: self.llm,
            amap_tool_factory=amap_factory,
            unsplash_factory=lambda: self.unsplash,
        ))
        app.dependency_overrides[get_app_runtime] = lambda: runtime
        return runtime

    def _terminal(self, run_id, timeout=10.0):
        deadline = time.time() + timeout
        last_status = None
        while time.time() < deadline:
            body = self.client.get(f"/api/trip/runs/{run_id}").json()
            last_status = body["status"]
            if last_status in TERMINAL_STATUSES:
                return body
            time.sleep(0.02)
        self.fail(f"run {run_id} 未在 {timeout}s 内到达终态，最后状态={last_status}")

    def test_transient_search_failure_retries_only_failed_step_and_recovers(self):
        """景点瞬时失败重试恢复：只重跑景点，天气/酒店不重跑；失败证据保留，终态 degraded 带真实计划。"""
        flaky = FlakyAttractionOnceSearch()
        flaky_amap = StubAmapTool()
        flaky_amap.tools["amap_maps_text_search"] = flaky
        self.runtime.close()
        self.runtime = self._runtime(lambda: flaky_amap)

        run = self.client.post("/api/trip/plan", json=REQUEST).json()
        body = self._terminal(run["run_id"])

        # 重试恢复后证据保留 -> 显式 degraded，但真实计划不被丢弃
        self.assertEqual(body["status"], "degraded")
        self.assertTrue(
            any("工具 amap_maps_text_search 执行失败" in w and "景点" in w for w in body["warnings"]),
            f"重试前的瞬时失败证据必须保留，实际 {body['warnings']}",
        )
        result = body["result"]
        self.assertIsNotNone(result)
        self.assertTrue(result["days"], "瞬时失败恢复后不应丢弃真实计划")

        # 重试隔离：只有景点步骤被重跑（2 次），天气/酒店各 1 次
        self.assertEqual(flaky.attraction_calls, 2, "景点必须在首次失败后重试一次（共 2 次调用）")
        self.assertEqual(flaky.hotel_calls, 1, "酒店搜索不得因景点重试而重跑")
        self.assertEqual(len(flaky_amap.tools["amap_maps_weather"].calls), 1, "天气查询不得重跑")

        # 每步 loguru 诊断：attractions 以 recovered 记录，含 run_id / elapsed_ms
        records = self.log_records
        recovered = [
            r for r in records
            if r.startswith("step_completed") and f"run_id={run['run_id']}" in r
            and "step=attractions" in r and "status=recovered" in r and "elapsed_ms=" in r
        ]
        self.assertEqual(len(recovered), 1, "必须有 attractions recovered 记录，实际:\n" + "\n".join(records))
        self.assertTrue(
            any("step_retrying" in r and "step=attractions" in r and "next_attempt=2" in r for r in records),
            "重试发生时必须有 step_retrying 诊断记录",
        )
        # 未失败步骤以 success 记录
        for step in ("weather", "hotels"):
            self.assertTrue(
                any(
                    r.startswith("step_completed") and f"step={step}" in r and "status=success" in r
                    for r in records
                ),
                f"步骤 {step} 应记录 success，实际:\n" + "\n".join(records),
            )

    def test_search_exhaustion_degrades_after_three_attempts(self):
        """景点始终失败：3 次尝试耗尽 -> 显式 degraded 空壳，不伪造成功，规划不执行。"""
        always_fail = AttractionAlwaysFailSearch()
        failing_amap = StubAmapTool()
        failing_amap.tools["amap_maps_text_search"] = always_fail
        self.runtime.close()
        self.runtime = self._runtime(lambda: failing_amap)

        run = self.client.post("/api/trip/plan", json=REQUEST).json()
        body = self._terminal(run["run_id"])

        self.assertEqual(body["status"], "degraded")
        self.assertTrue(body["warnings"], "耗尽必须携带失败清单")
        result = body["result"]
        self.assertEqual(result["days"], [], "耗尽不得伪造具体行程")
        self.assertFalse(
            any("请根据以下信息生成" in q for q in self.llm.recorded_queries),
            "搜索步骤耗尽时不得触发规划步骤",
        )
        # 重试有界：恰好 3 次尝试
        self.assertEqual(always_fail.attraction_calls, 3, "景点重试上限必须恰好为 3 次")
        self.assertEqual(always_fail.hotel_calls, 0, "首个步骤耗尽时应立即降级，不继续后续搜索")

        # 每步 loguru 诊断：step_exhausted 携带 attempts / max_attempts / elapsed_ms / error
        exhausted = [
            r for r in self.log_records
            if r.startswith("step_exhausted") and f"run_id={run['run_id']}" in r
            and "step=attractions" in r and "attempts=3" in r and "max_attempts=3" in r and "elapsed_ms=" in r
        ]
        self.assertEqual(len(exhausted), 1, "必须有 step_exhausted 记录，实际:\n" + "\n".join(self.log_records))


if __name__ == "__main__":
    unittest.main()