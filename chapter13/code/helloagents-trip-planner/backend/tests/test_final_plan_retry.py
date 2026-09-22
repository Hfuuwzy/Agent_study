"""最终规划步骤有界重试的 API 缝回归测试（工单 06 / 评测集样例 4）。

场景：模型输出 JSON 解码 / TripPlan schema 校验失败时，只重试最终规划步骤
（总尝试上限 3 次），三个搜索步骤不重跑；重试内恢复 -> success；
始终非法 -> 显式 failed（不伪造成功）。

运行方式（在 backend 目录下）：
    python -m unittest tests.test_final_plan_retry -v

全程离线：LLM / 高德 MCP / Unsplash 均为桩实现，不触碰真实 Key 与网络。
"""

import json
import time
import unittest

from fastapi.testclient import TestClient

from app.api.main import app
from app.runtime.factory import AppRuntime, RuntimeFactory, get_app_runtime
from tests.stubs import StubAmapTool, StubLLM, StubUnsplash

REQUEST = {
    "city": "上海", "start_date": "2026-10-01", "end_date": "2026-10-03",
    "travel_days": 3, "transportation": "公共交通", "accommodation": "经济型酒店",
    "preferences": ["历史文化"], "free_text_input": "",
}

TERMINAL_STATUSES = ("success", "degraded", "failed")

#: 可解析为 JSON 但缺失必填字段（overall_suggestions），TripPlan 校验必然失败。
SCHEMA_INVALID_PLAN = json.dumps(
    {"city": "上海", "start_date": "2026-10-01", "end_date": "2026-10-03", "days": []},
    ensure_ascii=False,
)


class ScriptedPlanLLM(StubLLM):
    """按调用顺序返回规划提示词回答；耗尽后重复最后一个响应（None 表示合法计划）。

    重试是否发生由生产代码决定：本桩只回答"每次规划器运行返回什么"，不自行实现
    重试。plan_invocations 记录规划提示词实际被调用的次数，供断言重试次数。
    """

    def __init__(self, plan_responses, **kwargs):
        super().__init__(**kwargs)
        self.plan_responses = list(plan_responses)
        self.plan_invocations = 0

    def invoke(self, messages, **kwargs):
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if "请根据以下信息生成" in last_user:
            self.plan_invocations += 1
            idx = min(self.plan_invocations - 1, len(self.plan_responses) - 1)
            response = self.plan_responses[idx]
            return response if response is not None else self._plan_json()
        return super().invoke(messages, **kwargs)


class FinalPlanRetryHttpTest(unittest.TestCase):
    """经公开 HTTP API 验证最终规划有界重试（测试缝 = 公开 HTTP 契约）。"""

    def setUp(self):
        self.amap = StubAmapTool()
        self.unsplash = StubUnsplash()
        self.llm = None
        self.runtime = None
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        if self.runtime is not None:
            self.runtime.close()
        app.dependency_overrides.clear()

    def _runtime(self, llm):
        self.llm = llm
        self.runtime = AppRuntime(factory=RuntimeFactory(
            llm_factory=lambda: self.llm,
            amap_tool_factory=lambda: self.amap,
            unsplash_factory=lambda: self.unsplash,
        ))
        app.dependency_overrides[get_app_runtime] = lambda: self.runtime
        return self.runtime

    def _scripted_llm(self, plan_responses):
        return ScriptedPlanLLM(
            plan_responses,
            city="上海", start_date="2026-10-01", end_date="2026-10-03", travel_days=3,
        )

    def _terminal(self, run_id, timeout=10.0):
        """轮询状态查询端点直到终态，返回终态响应体。"""
        deadline = time.time() + timeout
        last_status = None
        while time.time() < deadline:
            body = self.client.get(f"/api/trip/runs/{run_id}").json()
            last_status = body["status"]
            if last_status in TERMINAL_STATUSES:
                return body
            time.sleep(0.02)
        self.fail(f"run {run_id} 未在 {timeout}s 内到达终态，最后状态={last_status}")

    def _tool_call_counts(self, run_id):
        """经 SSE 事件流统计各工具实际执行次数（公开缝，迟到订阅走历史重放）。"""
        with self.client.stream("GET", f"/api/trip/runs/{run_id}/events") as resp:
            self.assertEqual(resp.status_code, 200)
            counts = {}
            for block in "".join(resp.iter_text()).split("\n\n"):
                data = next(
                    (
                        line.split(":", 1)[1].strip()
                        for line in block.splitlines()
                        if line.startswith("data:")
                    ),
                    None,
                )
                if data:
                    payload = json.loads(data)
                    if payload.get("type") == "tool_call":
                        name = payload["data"]["tool_name"]
                        counts[name] = counts.get(name, 0) + 1
            return counts

    def _assert_searches_ran_once(self):
        """三个搜索步骤各执行一次：天气 1 次，景点/酒店 text_search 各 1 次。"""
        self.assertEqual(
            len(self.amap.tools["amap_maps_weather"].calls), 1, "天气查询必须只执行一次"
        )
        text_calls = self.amap.tools["amap_maps_text_search"].calls
        self.assertEqual(len(text_calls), 2, "text_search 只应被景点/酒店两步调用")
        attraction = [c for c in text_calls if "历史文化" in str(c.get("keywords", ""))]
        hotel = [c for c in text_calls if "酒店" in str(c.get("keywords", ""))]
        self.assertEqual(len(attraction), 1, "景点搜索必须只执行一次")
        self.assertEqual(len(hotel), 1, "酒店搜索必须只执行一次")

    def test_json_invalid_once_then_valid_reaches_success(self):
        """JSON 解码失败一次后恢复：重试一次即 success，规划器共运行 2 次。"""
        llm = self._scripted_llm(["不是 JSON", None])
        self._runtime(llm)
        body = self._terminal(self.client.post("/api/trip/plan", json=REQUEST).json()["run_id"])

        self.assertEqual(body["status"], "success", "重试恢复必须到达合法终态 success")
        self.assertEqual(body["warnings"], [])
        self.assertEqual(body["result"]["city"], "上海")
        self.assertEqual(llm.plan_invocations, 2, "非法一次后重试一次，共 2 次规划器运行")
        self._assert_searches_ran_once()

    def test_schema_invalid_once_then_valid_reaches_success(self):
        """schema 非法（缺必填字段）一次后恢复：重试一次即 success，规划器共运行 2 次。"""
        llm = self._scripted_llm([SCHEMA_INVALID_PLAN, None])
        self._runtime(llm)
        body = self._terminal(self.client.post("/api/trip/plan", json=REQUEST).json()["run_id"])

        self.assertEqual(body["status"], "success", "schema 校验失败重试恢复必须 success")
        self.assertEqual(body["warnings"], [])
        self.assertEqual(body["result"]["city"], "上海")
        self.assertEqual(llm.plan_invocations, 2)
        self._assert_searches_ran_once()

    def test_always_invalid_json_exhausts_three_attempts_then_failed(self):
        """始终 JSON 非法：3 次尝试全部失败 -> 显式 failed，搜索步骤不重跑。"""
        llm = self._scripted_llm(["不是 JSON"])
        self._runtime(llm)
        accept = self.client.post("/api/trip/plan", json=REQUEST).json()
        body = self._terminal(accept["run_id"])

        self.assertEqual(body["status"], "failed", "重试耗尽必须显式 failed")
        self.assertTrue(body["error"], "failed 终态必须携带错误原因")
        self.assertTrue(body["warnings"], "failed 终态必须携带告警清单")
        self.assertIsNone(body["result"])
        self.assertEqual(llm.plan_invocations, 3, "总尝试次数必须恰好为 3 次")
        self._assert_searches_ran_once()
        self.assertEqual(
            self._tool_call_counts(accept["run_id"]),
            {"amap_maps_text_search": 2, "amap_maps_weather": 1},
            "SSE 事件流中搜索工具执行次数不得因规划重试而增加",
        )

    def test_schema_invalid_exhaustion_fails_after_three_attempts(self):
        """始终 schema 非法：3 次尝试全部校验失败 -> 显式 failed，搜索步骤不重跑。"""
        llm = self._scripted_llm([SCHEMA_INVALID_PLAN])
        self._runtime(llm)
        accept = self.client.post("/api/trip/plan", json=REQUEST).json()
        body = self._terminal(accept["run_id"])

        self.assertEqual(body["status"], "failed", "schema 重试耗尽必须显式 failed")
        self.assertTrue(body["error"])
        self.assertIsNone(body["result"])
        self.assertEqual(llm.plan_invocations, 3, "总尝试次数必须恰好为 3 次")
        self._assert_searches_ran_once()


if __name__ == "__main__":
    unittest.main()
