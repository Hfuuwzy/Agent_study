"""Public HTTP regression for planner and SSE executor isolation."""

import threading
import time
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import trip as trip_routes
from app.runtime.factory import AppRuntime, RuntimeFactory
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


class PlannerExecutorIsolationHttpTest(unittest.TestCase):
    """Verify executor isolation only through the public trip HTTP API."""

    def test_open_sse_stream_does_not_delay_second_run_or_health(self) -> None:
        """An idle SSE wait must not consume capacity needed by another planner."""
        release_first_planner = threading.Event()
        first_planner_entered = threading.Event()
        factory_lock = threading.Lock()
        amap_constructions = 0

        def build_amap_tool() -> StubAmapTool:
            nonlocal amap_constructions
            with factory_lock:
                amap_constructions += 1
                construction_number = amap_constructions
            if construction_number == 1:
                first_planner_entered.set()
                release_first_planner.wait(timeout=5.0)
            return StubAmapTool()

        runtime = AppRuntime(
            factory=RuntimeFactory(
                llm_factory=StubLLM,
                amap_tool_factory=build_amap_tool,
                unsplash_factory=StubUnsplash,
            ),
            planner_max_workers=2,
        )
        self.addCleanup(runtime.close)
        test_app = FastAPI()
        test_app.state.app_runtime = runtime
        test_app.include_router(trip_routes.router, prefix="/api")
        sse_statuses: list[int] = []

        with TestClient(test_app) as client:
            first = client.post("/api/trip/plan", json=VALID_REQUEST).json()
            self.assertTrue(first_planner_entered.wait(timeout=1.0), "首个 planner 必须进入阻塞构造")

            reader_started = threading.Event()

            def read_open_stream() -> None:
                reader_started.set()
                with client.stream("GET", f"/api/trip/runs/{first['run_id']}/events") as response:
                    sse_statuses.append(response.status_code)
                    "".join(response.iter_text())

            reader = threading.Thread(target=read_open_stream, name="test-sse-reader")
            reader.start()
            self.assertTrue(reader_started.wait(timeout=1.0), "SSE 读取线程必须启动")
            time.sleep(0.1)

            try:
                started_at = time.monotonic()
                second = client.post("/api/trip/plan", json=VALID_REQUEST)
                health = client.get("/api/trip/health")
                request_elapsed = time.monotonic() - started_at

                deadline = time.monotonic() + 0.75
                second_status = "running"
                while time.monotonic() < deadline:
                    second_status = client.get(
                        f"/api/trip/runs/{second.json()['run_id']}"
                    ).json()["status"]
                    if second_status == "success":
                        break
                    time.sleep(0.01)

                self.assertEqual(second.status_code, 202)
                self.assertEqual(health.status_code, 200)
                self.assertLess(request_elapsed, 0.5, "开放 SSE 时 POST 与健康检查不得延迟")
                self.assertEqual(
                    second_status,
                    "success",
                    "开放 SSE 不得占用第二个 planner 构造与执行所需的 executor 容量",
                )
            finally:
                release_first_planner.set()
                reader.join(timeout=5.0)

            self.assertFalse(reader.is_alive(), "SSE 流必须随首个 run 终态结束")
            self.assertEqual(sse_statuses, [200])


if __name__ == "__main__":
    unittest.main()
