"""评测运行器：把场景经唯一公开 HTTP API 缝（FastAPI TestClient）跑成类型化结果。

测试缝 = 公开 HTTP 契约（spec "Testing Decisions"）：本模块只做 HTTP 驱动与收集，
不做断言（断言在 ``checks``）。测试与未来评测 CLI 共用：

    run = run_scenario(scenario)     # 构造新鲜桩运行时 -> 受理 -> 轮询终态 -> 读 SSE
    assert_scenario(run)             # 逐条断言（checks 模块）

隔离规则：
- 每次运行都构造**全新**的桩与运行时，不以任何方式复用上一次运行的状态；
- 依赖覆写经 ``override_app_runtime`` 临时安装并恢复，不动其他 dependency overrides；
- TestClient 以上下文管理器运行（受理、轮询、订阅跨请求共享同一事件循环）。
"""

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.api.main import app
from app.runtime.factory import AppRuntime, RuntimeFactory, get_app_runtime

from .scenario_models import ExpectAccepted, Scenario
from .stubs import StubProbe, build_stub_probe

#: 终态集合（与公开契约一致）；轮询据此停止。
TERMINAL_STATUSES = ("success", "degraded", "failed")


@dataclass(frozen=True)
class SseEventRecord:
    """一条已解析的 SSE 事件（信任边界已把 JSON 载荷压成类型化字段）。"""

    type: str
    run_id: str
    data: dict[str, object]


@dataclass(frozen=True)
class ScenarioRun:
    """一次场景运行的 HTTP 观测结果：构造一次、只读观测，供断言与未来 CLI 使用。"""

    scenario: Scenario
    http_status: int
    acceptance: dict[str, object] | None
    run_id: str | None
    terminal: dict[str, object] | None
    events: list[SseEventRecord]
    sse_content_type: str | None
    validation_detail: list[dict[str, object]] | None
    photo: dict[str, object] | None
    health_runs_total: int | None
    probe: StubProbe
    elapsed_seconds: float

    @property
    def planner_queries(self) -> list[str]:
        """发给规划 Agent 的查询文本（按结构化触发标记筛选，非提示词措辞断言）。"""
        return [q for q in self.probe.llm.recorded_queries if PLANNER_TRIGGER in q]


#: 规划提示词的结构化触发标记（与 StubLLM / 生产查询模板一致）。
PLANNER_TRIGGER = "请根据以下信息生成"


def parse_sse_events(text: str) -> list[SseEventRecord]:
    """把 SSE 文本解析为事件记录列表；忽略心跳注释行与不完整帧。"""
    records: list[SseEventRecord] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block or block.startswith(":"):
            continue
        data_lines = [
            line.split(":", 1)[1].strip()
            for line in block.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            continue
        payload = json.loads("\n".join(data_lines))
        if not isinstance(payload, dict):
            continue
        event_type = payload.get("type")
        run_id = payload.get("run_id")
        data = payload.get("data")
        if isinstance(event_type, str) and isinstance(run_id, str) and isinstance(data, dict):
            records.append(SseEventRecord(type=event_type, run_id=run_id, data=dict(data)))
    return records


def as_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AssertionError(f"HTTP JSON 载荷应为对象，实际 {type(value).__name__}: {value!r}")
    return value


def as_str(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise AssertionError(f"字段 {key} 应为字符串，实际 {value!r}")
    return value


@contextmanager
def override_app_runtime(runtime: AppRuntime) -> Iterator[None]:
    """临时覆写 ``get_app_runtime`` 依赖：进入保存既有覆写，退出原样恢复。

    只触碰这一个键；其他 dependency overrides 一律不读取、不清除、不改写。
    """
    overrides = app.dependency_overrides
    had_override = get_app_runtime in overrides
    previous = overrides.get(get_app_runtime)
    overrides[get_app_runtime] = lambda: runtime
    try:
        yield
    finally:
        if had_override and previous is not None:
            overrides[get_app_runtime] = previous
        else:
            overrides.pop(get_app_runtime, None)


def poll_terminal(client: TestClient, run_id: str, timeout: float = 15.0) -> dict[str, object]:
    """有界轮询状态查询端点直到终态；超时视为运行失败（调用方可见）。"""
    deadline = time.monotonic() + timeout
    last_status: str | None = None
    while time.monotonic() < deadline:
        body = as_dict(client.get(f"/api/trip/runs/{run_id}").json())
        last_status = as_str(body, "status")
        if last_status in TERMINAL_STATUSES:
            return body
        time.sleep(0.02)
    raise TimeoutError(f"run {run_id} 未在 {timeout:.1f}s 内到达终态，最后状态={last_status}")


def read_sse_events(client: TestClient, run_id: str) -> tuple[list[SseEventRecord], str]:
    """读取完整 SSE 流（终态后订阅即全量历史重放 + 立即结束）并返回内容类型。"""
    with client.stream("GET", f"/api/trip/runs/{run_id}/events") as resp:
        content_type = resp.headers.get("content-type", "").split(";")[0].strip()
        text = "".join(resp.iter_text())
    return parse_sse_events(text), content_type


def run_scenario(scenario: Scenario) -> ScenarioRun:
    """用全新桩运行时把场景跑一遍公开 HTTP 缝，返回类型化观测结果（离线、不写盘）。"""
    probe = build_stub_probe(scenario)
    runtime = AppRuntime(
        factory=RuntimeFactory(
            llm_factory=lambda: probe.llm,
            amap_tool_factory=lambda: probe.amap,
            unsplash_factory=lambda: probe.unsplash,
        )
    )
    started = time.monotonic()
    try:
        with override_app_runtime(runtime):
            with TestClient(app) as client:
                return _collect(client, scenario, probe, time.monotonic() - started)
    finally:
        runtime.close()


def _collect(
    client: TestClient,
    scenario: Scenario,
    probe: StubProbe,
    elapsed_seconds: float,
) -> ScenarioRun:
    response = client.post("/api/trip/plan", json=scenario.request)
    http_status = response.status_code

    health_total = _health_runs_total(client)

    if http_status != 202:
        detail_value = as_dict(response.json()).get("detail")
        detail = [as_dict(item) for item in detail_value] if isinstance(detail_value, list) else None
        return ScenarioRun(
            scenario=scenario,
            http_status=http_status,
            acceptance=None,
            run_id=None,
            terminal=None,
            events=[],
            sse_content_type=None,
            validation_detail=detail,
            photo=None,
            health_runs_total=health_total,
            probe=probe,
            elapsed_seconds=elapsed_seconds,
        )

    acceptance = as_dict(response.json())
    run_id = as_str(acceptance, "run_id")
    terminal = poll_terminal(client, run_id)
    events, sse_content_type = read_sse_events(client, run_id)
    photo = None
    if isinstance(scenario.expect, ExpectAccepted) and scenario.expect.assert_photo_miss_contract:
        photo = as_dict(client.get("/api/poi/photo", params={"name": "外滩"}).json())

    return ScenarioRun(
        scenario=scenario,
        http_status=http_status,
        acceptance=acceptance,
        run_id=run_id,
        terminal=terminal,
        events=events,
        sse_content_type=sse_content_type,
        validation_detail=None,
        photo=photo,
        health_runs_total=health_total,
        probe=probe,
        elapsed_seconds=elapsed_seconds,
    )


def _health_runs_total(client: TestClient) -> int | None:
    """读取健康检查的 runs_total（请求层拒绝断言：422 时该值必须保持不变）。"""
    body = as_dict(client.get("/api/trip/health").json())
    value = body.get("runs_total")
    return value if isinstance(value, int) else None