"""请求层校验测试：非法请求在 API 层被 422 拒绝，不触发一次 Agent 运行（评测集样例 2）。

测试缝 = 公开 HTTP API（POST /api/trip/plan，FastAPI TestClient + 注入桩运行时），
与 spec.md Testing Decisions 一致：只断言 HTTP 状态码与错误载荷，不触碰校验实现细节。
"""

import time
import unittest

from fastapi.testclient import TestClient

from app.api.main import app
from app.runtime.factory import AppRuntime, RuntimeFactory, get_app_runtime
from tests.stubs import StubAmapTool, StubLLM, StubUnsplash

VALID_REQUEST = {
    "city": "上海", "start_date": "2026-10-01", "end_date": "2026-10-03",
    "travel_days": 3, "transportation": "公共交通", "accommodation": "经济型酒店",
    "preferences": ["历史文化"], "free_text_input": "",
}


class RequestValidationHttpTest(unittest.TestCase):
    def setUp(self):
        self.llm = StubLLM(city="上海", start_date="2026-10-01", end_date="2026-10-03", travel_days=3)
        self.amap = StubAmapTool()
        self.unsplash = StubUnsplash()
        self.runtime = AppRuntime(factory=RuntimeFactory(
            llm_factory=lambda: self.llm,
            amap_tool_factory=lambda: self.amap,
            unsplash_factory=lambda: self.unsplash,
        ))
        app.dependency_overrides[get_app_runtime] = lambda: self.runtime
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.runtime.close()
        app.dependency_overrides.clear()

    def _terminal(self, run_id):
        """有界轮询等待 Run 进入终态并返回状态查询体（超时则 fail）。"""
        deadline = time.time() + 5
        while time.time() < deadline:
            body = self.client.get(f"/api/trip/runs/{run_id}").json()
            if body["status"] in {"success", "degraded", "failed"}:
                return body
            time.sleep(0.01)
        self.fail("run did not reach terminal state")

    def _reject(self, payload, expected_msg, expected_loc=None):
        """断言一次非法请求：422 + 明确错误信息 + 零 Run 受理 + 零 Agent 调用。"""
        resp = self.client.post("/api/trip/plan", json=payload)
        self.assertEqual(resp.status_code, 422)
        detail = resp.json()["detail"]
        self.assertTrue(
            any(expected_msg in err.get("msg", "") for err in detail),
            f"预期错误消息包含 {expected_msg!r}，实际 {detail}",
        )
        if expected_loc is not None:
            self.assertTrue(
                any(list(err.get("loc", [])) == expected_loc for err in detail),
                f"预期错误定位 {expected_loc}，实际 {detail}",
            )
        # 校验失败发生在路由受理之前：不产生 Run（经公开 health 端点断言）、不调用 LLM
        health = self.client.get("/api/trip/health").json()
        self.assertEqual(health["runs_total"], 0, "非法请求不应受理 Run")
        self.assertEqual(self.llm.calls, 0, "非法请求不应触发 Agent 运行")
        self.assertEqual(self.llm.recorded_queries, [], "非法请求不应触发 Agent 运行")
        return detail

    def test_missing_date_field_is_rejected_before_run(self):
        # 评测集样例 2：缺日期字段 → 请求层拒绝（非 Agent 运行期错误）
        payload = {k: v for k, v in VALID_REQUEST.items() if k != "end_date"}
        self._reject(payload, "Field required", ["body", "end_date"])

    def test_date_wrong_type_is_rejected(self):
        payload = dict(VALID_REQUEST, start_date=20260601)
        self._reject(payload, "valid string", ["body", "start_date"])

    def test_invalid_date_format_is_rejected(self):
        for bad in ("2026/10/01", "2026-2-01", "20260201", " 2026-10-01", "２０２６-０２-０１"):
            with self.subTest(bad=bad):
                payload = dict(VALID_REQUEST, start_date=bad)
                self._reject(payload, "YYYY-MM-DD", ["body", "start_date"])

    def test_impossible_calendar_date_is_rejected(self):
        for bad in ("2026-02-30", "2026-04-31", "2026-00-01", "2026-13-01", "0000-01-01"):
            with self.subTest(bad=bad):
                payload = dict(VALID_REQUEST, end_date=bad)
                self._reject(payload, "非法日期", ["body", "end_date"])

    def test_end_before_start_is_rejected(self):
        payload = dict(VALID_REQUEST, end_date="2026-09-30")
        self._reject(payload, "结束日期不能早于开始日期", ["body"])

    def test_travel_days_mismatch_with_date_range_is_rejected(self):
        # 日期区间 2026-10-01 ~ 2026-10-03 含首尾 3 天，travel_days 必须为 3
        for wrong in (1, 2, 4):
            with self.subTest(wrong=wrong):
                payload = dict(VALID_REQUEST, travel_days=wrong)
                self._reject(payload, "travel_days 与日期区间不一致", ["body"])

    def test_travel_days_out_of_bounds_is_rejected(self):
        for wrong in (0, 31):
            with self.subTest(wrong=wrong):
                payload = dict(VALID_REQUEST, travel_days=wrong)
                self._reject(payload, "greater than or equal to 1" if wrong == 0 else "less than or equal to 30", ["body", "travel_days"])

    def test_valid_request_is_accepted_and_executes(self):
        resp = self.client.post("/api/trip/plan", json=VALID_REQUEST)
        self.assertEqual(resp.status_code, 202)
        body = resp.json()
        self.assertTrue(body["run_id"])
        self.assertEqual(body["status"], "pending")
        self.assertEqual(self.client.get("/api/trip/health").json()["runs_total"], 1)
        # 一致请求不受误伤：后台执行走桩成功终态
        status = self._terminal(body["run_id"])
        self.assertEqual(status["status"], "success")

    def test_boundary_date_ranges_are_accepted(self):
        cases = [
            # 闰日单天、月末跨月、跨年、30 天上限
            ("2028-02-29", "2028-02-29", 1),
            ("2026-01-31", "2026-02-01", 2),
            ("2026-12-31", "2027-01-01", 2),
            ("2026-10-01", "2026-10-30", 30),
        ]
        for start, end, days in cases:
            with self.subTest(start=start, end=end, days=days):
                payload = dict(VALID_REQUEST, start_date=start, end_date=end, travel_days=days)
                resp = self.client.post("/api/trip/plan", json=payload)
                self.assertEqual(resp.status_code, 202, resp.text)
                self.assertTrue(resp.json()["run_id"])


if __name__ == "__main__":
    unittest.main()
