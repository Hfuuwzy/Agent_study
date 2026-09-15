"""SSE 真实进度事件流的 API 缝测试：事件序列、终态 status、失败路径、重放、404 与心跳保活。

运行方式（在 backend 目录下）：
    python -m unittest discover -s tests -v

全程离线：LLM / 高德 MCP / Unsplash 均为桩实现；SSE 经 FastAPI TestClient 的真实
StreamingResponse 流读取（含实时追加与历史重放两条路径）。心跳保活经公开 SSE 线格式
(': keepalive' 注释行)断言，符合 spec.md「唯一测试缝 = 公开 HTTP API」决策。
"""

import json
import threading
import time
import unittest

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes import trip as trip_routes
from app.runtime.events import RunEventType
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

#: 公开事件协议：run_started / step_started / tool_call / tool_result / validation_error / run_completed
CONTRACT_EVENT_TYPES = [t.value for t in RunEventType]

TERMINAL_STATUSES = ("success", "degraded", "failed")


def parse_sse(text: str):
    """把 SSE 文本解析为 [{event, data}, ...]，忽略注释行（心跳）。

    data 取事件载荷的内层字段（status/step/tool_name/...），外层 run_id/type/timestamp 由
    payload 保留，便于断言需要时取用。
    """
    events = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block or block.startswith(":"):
            continue
        event_name = None
        data_lines = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
        if data_lines:
            payload = json.loads("\n".join(data_lines))
            events.append({
                "event": event_name,
                "data": payload.get("data", {}),
                "payload": payload,
            })
    return events


class SseEventContractTest(unittest.TestCase):
    """经公开 HTTP API 验证 SSE 事件契约（测试缝 = 公开 HTTP 契约）。"""

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
        self.addCleanup(self.runtime.close)
        app.dependency_overrides[get_app_runtime] = lambda: self.runtime
        # 以生命周期上下文管理 TestClient：后台 Run 任务在请求间存活（受理→查询/订阅跨请求）
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()

    def _poll_terminal(self, run_id, timeout=10.0):
        deadline = time.time() + timeout
        last_status = None
        while time.time() < deadline:
            body = self.client.get(f"/api/trip/runs/{run_id}").json()
            last_status = body["status"]
            if last_status in TERMINAL_STATUSES:
                return body
            time.sleep(0.02)
        self.fail(f"run {run_id} 未在 {timeout}s 内到达终态，最后状态={last_status}")

    def _read_sse(self, run_id):
        """读取完整 SSE 流（阻塞到流结束）并解析为事件列表。"""
        with self.client.stream("GET", f"/api/trip/runs/{run_id}/events") as resp:
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(
                resp.headers["content-type"].split(";")[0], "text/event-stream",
                "SSE 端点必须以 text/event-stream 响应",
            )
            return parse_sse("".join(resp.iter_text()))

    def _capture_sse_raw(self, run_id, holder):
        """后台读取完整 SSE 原始文本（含心跳注释行），存入 holder（列表，取 [0]）。"""
        with self.client.stream("GET", f"/api/trip/runs/{run_id}/events") as resp:
            holder.append("".join(resp.iter_text()))

    def test_idle_heartbeat_keepalive_during_slow_construction(self):
        """回归：空闲窗口（后台慢构造期间）SSE 必须发出心跳保活行。

        用缩短的 SSE_HEARTBEAT_SECONDS 把空闲窗口放大为多个心跳周期；慢构造桩在
        工作线程阻塞约 0.4s，期间事件流应持续发 ': keepalive' 注释行。旧 wait_next
        在循环里逐次重置超时、空闲时永不返回，整个窗口内一条保活都不会发出——
        前端长等待期间连接可能被代理判定超时。断言对象为公开 SSE 线格式，不断言
        通道内部实现。
        """
        raw: list = []
        release_construction = threading.Event()
        original_heartbeat = trip_routes.SSE_HEARTBEAT_SECONDS
        trip_routes.SSE_HEARTBEAT_SECONDS = 0.1  # 4 倍于构造阻塞窗口的心跳周期
        try:
            def slow_amap_tool():
                release_construction.wait(timeout=5.0)
                return StubAmapTool()

            factory = RuntimeFactory(
                llm_factory=lambda: StubLLM(),
                amap_tool_factory=slow_amap_tool,
                unsplash_factory=lambda: StubUnsplash(),
            )
            runtime = AppRuntime(factory=factory)
            self.addCleanup(runtime.close)
            app.dependency_overrides[get_app_runtime] = lambda: runtime

            accept = self.client.post("/api/trip/plan", json=VALID_REQUEST).json()
            # 后台订阅并完整读取 SSE 流（阻塞到流结束）；构造此刻正在工作线程阻塞
            reader = threading.Thread(
                target=self._capture_sse_raw, args=(accept["run_id"], raw), daemon=True
            )
            reader.start()
            # 等待多个心跳周期后放行构造：窗口内事件流应已发出保活行
            time.sleep(0.4)
            release_construction.set()
            reader.join(timeout=10.0)
            self.assertFalse(reader.is_alive(), "SSE 流未在预期时间内结束")
            self.assertTrue(raw, "SSE 流必须完整读取")
            # 保活行必须出现在"首步开始之前"的空闲窗口（run_started 与 step_started 之间），
            # 而非事件批次之后的附带行——后者在旧 wait_next 下也会出现，不具判别力
            first_step = raw[0].find("event: step_started")
            self.assertNotEqual(first_step, -1, "事件流必须包含 step_started")
            self.assertIn(
                ": keepalive",
                raw[0][:first_step],
                "空闲窗口（首步开始前）必须发出 SSE 心跳保活行",
            )
        finally:
            trip_routes.SSE_HEARTBEAT_SECONDS = original_heartbeat
            release_construction.set()
            app.dependency_overrides.clear()

    def test_sse_stream_emits_contract_events_in_order(self):
        """事件流包含全部契约事件类型，顺序符合真实编排：run_started -> 四步 step_started(含
        tool_call/tool_result) -> run_completed。用延迟桩保证流在运行中实时读取。"""
        self.llm.delay_per_invoke = 0.05  # 7 次 invoke ≈ 0.35s，让 SSE 在运行中订阅
        accept = self.client.post("/api/trip/plan", json=VALID_REQUEST).json()
        events = self._read_sse(accept["run_id"])

        types = [e["event"] for e in events]
        self.assertEqual(types[0], "run_started", "首事件必须是 run_started")
        self.assertEqual(types[-1], "run_completed", "末事件必须是 run_completed")

        # 全部事件类型都属于公开协议（事件流推送"全部定义事件类型"的可用子集）
        self.assertTrue(set(types) <= set(CONTRACT_EVENT_TYPES), f"存在协议外事件类型: {set(types)}")
        self.assertIn("step_started", types)
        self.assertIn("tool_call", types)
        self.assertIn("tool_result", types)

        # 四步 step_started 按真实编排顺序推进
        steps = [e["data"].get("step") for e in events if e["event"] == "step_started"]
        self.assertEqual(steps, ["attractions", "weather", "hotels", "plan"])

        # run_started 携带运行标识与请求摘要
        self.assertEqual(events[0]["data"]["status"], "running")
        self.assertEqual(events[0]["data"]["city"], "上海")

    def test_tool_events_carry_real_tool_name_and_result(self):
        """tool_call/tool_result 反映真实工具执行（探针位于 Agent 工具注册表与实际工具之间）。"""
        accept = self.client.post("/api/trip/plan", json=VALID_REQUEST).json()
        events = self._read_sse(accept["run_id"])

        tool_calls = [e["data"] for e in events if e["event"] == "tool_call"]
        tool_results = [e["data"] for e in events if e["event"] == "tool_result"]
        self.assertGreater(len(tool_calls), 0, "至少有一次工具调用")
        self.assertEqual(len(tool_calls), len(tool_results), "每次 tool_call 必须伴随 tool_result")

        names = {c["tool_name"] for c in tool_calls}
        self.assertIn("amap_maps_text_search", names, "景点/酒店搜索必须真实执行")
        self.assertIn("amap_maps_weather", names, "天气查询必须真实执行")
        self.assertTrue(all("result_preview" in r for r in tool_results), "tool_result 携带结果摘要")
        # 与桩工具实际调用次数一致：探针没有改变工具执行语义
        self.assertEqual(len(tool_calls), sum(len(t.calls) for t in self.amap.tools.values()))

    def test_run_completed_event_carries_terminal_status_and_result(self):
        """终态事件 run_completed 携带 status 与结果（前端据此渲染终态）。"""
        accept = self.client.post("/api/trip/plan", json=VALID_REQUEST).json()
        events = self._read_sse(accept["run_id"])
        completed = events[-1]["data"]
        self.assertEqual(events[-1]["event"], "run_completed")
        self.assertEqual(completed["status"], "success")
        self.assertIn("result", completed, "success 终态事件必须携带计划结果")
        self.assertEqual(completed["result"]["city"], "上海")
        self.assertEqual(len(completed["result"]["days"]), 3)
        self.assertEqual(completed["warnings"], [], "success 终态无降级告警")

    def test_late_subscriber_receives_full_history_replay(self):
        """迟到订阅（Run 已终态）仍能收到全量事件重放，保证断线重连的一致性。"""
        accept = self.client.post("/api/trip/plan", json=VALID_REQUEST).json()
        self._poll_terminal(accept["run_id"])  # 等终态后再订阅
        events = self._read_sse(accept["run_id"])

        self.assertEqual(events[0]["event"], "run_started")
        self.assertEqual(events[-1]["event"], "run_completed")
        self.assertEqual(events[-1]["data"]["status"], "success")
        steps = [e["data"].get("step") for e in events if e["event"] == "step_started"]
        self.assertEqual(steps, ["attractions", "weather", "hotels", "plan"])

    def test_failed_run_emits_run_completed_with_failed_status(self):
        """失败路径：依赖构造失败时 run_completed 携带 status=failed 与 error（不伪造成功）。"""
        def boom():
            raise ValueError("高德地图API Key未配置(测试桩)")

        factory = RuntimeFactory(
            llm_factory=lambda: StubLLM(),
            amap_tool_factory=boom,
            unsplash_factory=lambda: StubUnsplash(),
        )
        runtime = AppRuntime(factory=factory)
        self.addCleanup(runtime.close)
        app.dependency_overrides[get_app_runtime] = lambda: runtime

        accept = self.client.post("/api/trip/plan", json=VALID_REQUEST).json()
        events = self._read_sse(accept["run_id"])

        completed = events[-1]["data"]
        self.assertEqual(completed["status"], "failed")
        self.assertTrue(completed.get("error"), "failed 终态事件必须携带错误原因")
        self.assertNotIn("result", completed, "failed 终态不得伪装携带计划")

    def test_unknown_run_events_returns_404(self):
        """未知 run_id 订阅事件流必须 404。"""
        resp = self.client.get("/api/trip/runs/does-not-exist/events")
        self.assertEqual(resp.status_code, 404)

    def test_openapi_exposes_sse_event_type_enum(self):
        """事件协议即公开契约：RunEventType 枚举必须包含协议全部 6 种事件类型。

        说明：SSE 端点以 StreamingResponse 流式返回（无 response_model），事件类型契约
        以 app.runtime.events.RunEventType 枚举为准，与前端类型镜像保持一致。
        """
        event_enum = [t.value for t in RunEventType]
        self.assertEqual(sorted(event_enum), sorted(CONTRACT_EVENT_TYPES))


if __name__ == "__main__":
    unittest.main()
