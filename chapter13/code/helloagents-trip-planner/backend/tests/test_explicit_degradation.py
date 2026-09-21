import json
import time
import unittest

from fastapi.testclient import TestClient

from app.api.main import app
from app.runtime.factory import AppRuntime, RuntimeFactory, get_app_runtime
from tests.stubs import StubAmapTool, StubLLM, StubTool, StubUnsplash

REQUEST = {
    "city": "上海", "start_date": "2026-10-01", "end_date": "2026-10-03",
    "travel_days": 3, "transportation": "公共交通", "accommodation": "经济型酒店",
    "preferences": ["历史文化"], "free_text_input": "",
}


class MissUnsplash(StubUnsplash):
    def get_photo_url(self, query):
        self.calls.append(query)
        return None


class ErrorUnsplash(StubUnsplash):
    def get_photo_url(self, query):
        self.calls.append(query)
        raise RuntimeError("图片服务不可用")


def failing_amap():
    amap = StubAmapTool()
    amap.tools["amap_maps_text_search"] = StubTool(
        "amap_maps_text_search", "文本搜索POI", "", error=RuntimeError("搜索服务不可用")
    )
    return amap


class ExplicitDegradationHttpTest(unittest.TestCase):
    def setUp(self):
        self.llm = StubLLM(city="上海", start_date="2026-10-01", end_date="2026-10-03", travel_days=3)
        self.amap = StubAmapTool()
        self.unsplash = StubUnsplash()
        self.runtime = self._runtime(lambda: self.amap, lambda: self.unsplash)
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.runtime.close()
        app.dependency_overrides.clear()

    def _runtime(self, amap_factory, unsplash_factory, llm_factory=None):
        runtime = AppRuntime(factory=RuntimeFactory(
            llm_factory=llm_factory or (lambda: self.llm),
            amap_tool_factory=amap_factory,
            unsplash_factory=unsplash_factory,
        ))
        app.dependency_overrides[get_app_runtime] = lambda: runtime
        return runtime

    def _terminal(self, run_id):
        deadline = time.time() + 5
        while time.time() < deadline:
            body = self.client.get(f"/api/trip/runs/{run_id}").json()
            if body["status"] in {"success", "degraded", "failed"}:
                return body
            time.sleep(0.01)
        self.fail("run did not reach terminal state")

    def _sse_events(self, run_id):
        with self.client.stream("GET", f"/api/trip/runs/{run_id}/events") as response:
            self.assertEqual(response.status_code, 200)
            events = []
            for block in "".join(response.iter_text()).split("\n\n"):
                data = next((line.split(":", 1)[1].strip() for line in block.splitlines() if line.startswith("data:")), None)
                if data:
                    events.append(json.loads(data))
            return events

    def test_search_failure_is_degraded_empty_shell_and_does_not_plan(self):
        self.runtime.close()
        self.runtime = self._runtime(failing_amap, lambda: self.unsplash)
        run = self.client.post("/api/trip/plan", json=REQUEST).json()
        body = self._terminal(run["run_id"])
        self.assertEqual(body["status"], "degraded")
        self.assertTrue(body["warnings"])
        result = body["result"]
        self.assertEqual(result["city"], "上海")
        self.assertEqual(result["start_date"], REQUEST["start_date"])
        self.assertEqual(result["end_date"], REQUEST["end_date"])
        self.assertEqual(result["days"], [])
        self.assertEqual(result["weather_info"], [])
        self.assertIsNone(result["budget"])
        self.assertFalse(any(key in json.dumps(result) for key in ("longitude", "latitude")))
        self.assertFalse(any("请根据以下信息生成" in query for query in self.llm.recorded_queries))

    def test_empty_search_response_is_degraded(self):
        self.llm.tool_result_response = ""
        run = self.client.post("/api/trip/plan", json=REQUEST).json()
        body = self._terminal(run["run_id"])
        self.assertEqual(body["status"], "degraded")
        self.assertTrue(body["warnings"])

    def test_final_parse_failure_is_failed_with_warnings_and_no_result(self):
        self.llm.plan_response = "不是 JSON"
        run = self.client.post("/api/trip/plan", json=REQUEST).json()
        body = self._terminal(run["run_id"])
        self.assertEqual(body["status"], "failed")
        self.assertTrue(body["warnings"])
        self.assertIsNone(body["result"])
        events = self._sse_events(run["run_id"])
        completed = events[-1]["data"]
        self.assertEqual(completed["status"], body["status"])
        self.assertEqual(completed["warnings"], body["warnings"])
        self.assertNotIn("result", completed)

    def test_success_has_empty_warnings_and_sse_http_parity(self):
        run = self.client.post("/api/trip/plan", json=REQUEST).json()
        body = self._terminal(run["run_id"])
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["warnings"], [])
        completed = self._sse_events(run["run_id"])[-1]["data"]
        self.assertEqual(completed["status"], body["status"])
        self.assertEqual(completed["warnings"], body["warnings"])
        self.assertEqual(completed["result"], body["result"])

    def test_photo_hit_miss_and_error_are_explicit(self):
        hit = self.client.get("/api/poi/photo", params={"name": "外滩"}).json()
        self.assertFalse(hit["is_placeholder"])
        self.assertEqual(hit["warnings"], [])
        self.assertEqual(hit["photo_url"], self.unsplash.photo_url)

        self.runtime.close()
        self.runtime = self._runtime(lambda: self.amap, MissUnsplash)
        miss = self.client.get("/api/poi/photo", params={"name": "外滩"})
        self.assertEqual(miss.status_code, 200)
        self.assertIsNone(miss.json()["photo_url"])
        self.assertTrue(miss.json()["is_placeholder"])
        self.assertTrue(miss.json()["warnings"])

        self.runtime.close()
        self.runtime = self._runtime(lambda: self.amap, ErrorUnsplash)
        error = self.client.get("/api/poi/photo", params={"name": "外滩"})
        self.assertEqual(error.status_code, 200)
        self.assertIsNone(error.json()["photo_url"])
        self.assertTrue(error.json()["is_placeholder"])
        self.assertTrue(error.json()["warnings"])

    def test_warnings_are_isolated_between_runs(self):
        count = 0
        def amap_factory():
            nonlocal count
            count += 1
            return failing_amap() if count == 1 else StubAmapTool()
        self.runtime.close()
        self.runtime = self._runtime(amap_factory, lambda: self.unsplash)
        first = self._terminal(self.client.post("/api/trip/plan", json=REQUEST).json()["run_id"])
        second = self._terminal(self.client.post("/api/trip/plan", json=REQUEST).json()["run_id"])
        self.assertEqual(first["status"], "degraded")
        self.assertTrue(first["warnings"])
        self.assertEqual(second["status"], "success")
        self.assertEqual(second["warnings"], [])


if __name__ == "__main__":
    unittest.main()
