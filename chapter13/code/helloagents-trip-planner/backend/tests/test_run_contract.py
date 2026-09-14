"""Run 受理契约的 API 缝测试：TestClient + 桩运行时驱动公开 HTTP 契约（首个测试先例）。

运行方式（在 backend 目录下）：
    python -m unittest discover -s tests -v

全程离线：LLM / 高德 MCP / Unsplash 均为桩实现，不触碰真实 Key 与网络。
"""

import time
import unittest

from fastapi.testclient import TestClient

from app.api.main import app
from app.runtime.factory import AppRuntime, RuntimeFactory, get_app_runtime
from tests.stubs import StubAmapTool, StubLLM, StubUnsplash

VALID_REQUEST = {
    "city": "上海",
    "start_date": "2026-10-01",
    "end_date": "2026-10-03",
    "travel_days": 3,
    "transportation": "公共交通",
    "accommodation": "经济型酒店",
    "preferences": ["历史文化"],
    "free_text_input": "希望多安排一些博物馆",
}

# 契约中的五个状态（工单 01）
ALL_STATUSES = ("pending", "running", "success", "degraded", "failed")
TERMINAL_STATUSES = ("success", "degraded", "failed")


class RunContractTest(unittest.TestCase):
    """经公开 HTTP API 验证 Run 受理契约（测试缝 = 公开 HTTP 契约，不断言内部实现）。"""

    def setUp(self):
        self.llm = StubLLM(city="上海", start_date="2026-10-01", end_date="2026-10-03", travel_days=3)
        self.amap = StubAmapTool()
        self.unsplash = StubUnsplash()
        factory = RuntimeFactory(
            llm_factory=lambda: self.llm,
            amap_tool_factory=lambda: self.amap,
            unsplash_factory=lambda: self.unsplash,
        )
        self.runtime = AppRuntime(factory=factory)
        app.dependency_overrides[get_app_runtime] = lambda: self.runtime
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()

    def _poll_terminal(self, run_id, timeout=10.0):
        """轮询状态查询端点直到终态，返回终态响应体。"""
        deadline = time.time() + timeout
        last_status = None
        while time.time() < deadline:
            resp = self.client.get(f"/api/trip/runs/{run_id}")
            self.assertEqual(resp.status_code, 200, "状态查询端点必须对已受理的 run_id 返回 200")
            body = resp.json()
            last_status = body["status"]
            if last_status in TERMINAL_STATUSES:
                return body
            time.sleep(0.02)
        self.fail(f"run {run_id} 未在 {timeout}s 内到达终态，最后状态={last_status}")

    def test_post_plan_returns_acceptance_with_run_id(self):
        """验收 1：POST /trip/plan 立即返回受理结果与 run_id，不再同步返回计划。"""
        resp = self.client.post("/api/trip/plan", json=VALID_REQUEST)
        self.assertEqual(resp.status_code, 202)
        body = resp.json()
        self.assertIn("run_id", body)
        self.assertTrue(body["run_id"])
        self.assertIn(body["status"], ("pending", "running"))
        self.assertNotIn("data", body, "受理契约下不应同步携带计划")
        self.assertNotIn("success", body, "受理契约下不应再使用 success 字段")

    def test_run_reaches_success_with_stub_planner(self):
        """验收 4：真实编排链（含 TOOL_CALL 解析与工具执行）经桩运行时跑通并落 success。"""
        accept = self.client.post("/api/trip/plan", json=VALID_REQUEST).json()
        body = self._poll_terminal(accept["run_id"])
        self.assertEqual(body["status"], "success")
        result = body["result"]
        self.assertEqual(result["city"], "上海")
        self.assertEqual(len(result["days"]), 3)
        self.assertEqual(result["days"][0]["date"], "2026-10-01")
        self.assertEqual(result["days"][0]["day_index"], 0)

    def test_run_status_is_one_of_contract_enum(self):
        """验收 2：状态查询端点返回的值属于契约枚举的五个之一（受理与终态各验证一次）。"""
        accept = self.client.post("/api/trip/plan", json=VALID_REQUEST).json()
        self.assertIn(accept["status"], ALL_STATUSES)
        body = self._poll_terminal(accept["run_id"])
        self.assertIn(body["status"], ALL_STATUSES)
        # 终态响应必须同时携带结果，便于前端渲染
        self.assertIn("result", body)

    def test_unknown_run_returns_404(self):
        """未知 run_id 必须 404。"""
        resp = self.client.get("/api/trip/runs/does-not-exist")
        self.assertEqual(resp.status_code, 404)

    def test_run_failed_when_dependency_construction_fails(self):
        """失败路径：依赖构造失败时 Run 显式 failed + 携带 error（不伪造成功）。"""
        def boom():
            raise ValueError("高德地图API Key未配置(测试桩)")

        factory = RuntimeFactory(
            llm_factory=lambda: StubLLM(),
            amap_tool_factory=boom,
            unsplash_factory=lambda: StubUnsplash(),
        )
        runtime = AppRuntime(factory=factory)
        app.dependency_overrides[get_app_runtime] = lambda: runtime

        accept = self.client.post("/api/trip/plan", json=VALID_REQUEST).json()
        body = self._poll_terminal(accept["run_id"])
        self.assertEqual(body["status"], "failed")
        self.assertTrue(body["error"], "failed 终态必须携带错误原因")

    def test_stub_dependencies_are_actually_injected(self):
        """验收 3：LLM / 高德 MCP 均实际使用注入的桩（无真实 Key、无网络也能完整跑通）。"""
        accept = self.client.post("/api/trip/plan", json=VALID_REQUEST).json()
        body = self._poll_terminal(accept["run_id"])
        self.assertEqual(body["status"], "success")
        self.assertGreater(self.llm.calls, 0, "Run 必须实际调用注入的桩 LLM")
        self.assertTrue(self.amap.tools["amap_maps_text_search"].calls, "景点/酒店搜索桩工具必须被调用")
        self.assertTrue(self.amap.tools["amap_maps_weather"].calls, "天气桩工具必须被调用")
        # 结果内容来自桩 LLM 的固定数据，而非真实 Key 数据
        self.assertEqual(body["result"]["days"][0]["attractions"][0]["name"], "外滩")

    def test_unsplash_route_uses_injected_stub(self):
        """验收 3：Unsplash 可经运行时工厂注入桩（图片路由不触网）。"""
        resp = self.client.get("/api/poi/photo", params={"name": "外滩"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["photo_url"], self.unsplash.photo_url)
        self.assertTrue(self.unsplash.calls, "桩 Unsplash 必须被实际调用")

    def test_map_weather_route_uses_injected_amap_stub(self):
        """验收 3：手动地图路由（AmapService）经工厂注入桩工具（不拉起 MCP 子进程）。"""
        resp = self.client.get("/api/map/weather", params={"city": "上海"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertTrue(self.amap.tools["amap_maps_weather"].calls, "天气桩工具必须被实际调用")

    def test_trip_health_is_live_and_cheap(self):
        """健康检查不构造任何外部依赖即可响应（避免健康检查触发 MCP 子进程）。"""
        resp = self.client.get("/api/trip/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "healthy")
        self.assertEqual(body["runtime_factory"], "RuntimeFactory")


class RunStatusSchemaTest(unittest.TestCase):
    """契约枚举的 Schema 层验证：公开 OpenAPI 即公开契约。"""

    def test_openapi_exposes_run_status_enum_with_all_contract_values(self):
        schema = app.openapi()
        run_status_enum = schema["components"]["schemas"]["RunStatus"]["enum"]
        self.assertEqual(sorted(run_status_enum), sorted(ALL_STATUSES))


if __name__ == "__main__":
    unittest.main()
