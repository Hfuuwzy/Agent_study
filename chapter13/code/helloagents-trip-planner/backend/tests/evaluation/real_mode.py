"""真实 Key 快乐路径运行器（CLI ``--real`` 专属；默认离线评测绝不触碰本模块）。

仅当用户显式使用 ``--real --case happy_path`` 时才进入本模块：先预检真实配置
（LLM Key / 高德 Key / ``uvx`` 可用性），预检失败抛 :class:`RealPreflightError`
（CLI 映射为退出码 2，**绝不静默回退到桩**），随后经 ``AppRuntime.default()`` +
临时依赖覆写走同一条公开 HTTP 缝（POST 受理 -> GET 轮询终态 -> SSE 事件流）。

真实模式校验与离线断言解耦：只验证"上海 3 天 success 的结构完整"——日期/天数/餐饮/
酒店/景点坐标存在且为数值/天气/预算/总体建议 + 基础 SSE 契约，**不比较**桩夹具的
具体坐标或名称。外部 ``uvx`` 进程仅在此显式开关下可能自行管理其缓存。
"""

import os
import shutil
from dataclasses import dataclass
from typing import Final

from fastapi.testclient import TestClient

from app.api.main import app
from app.config import get_settings
from app.runtime.factory import AppRuntime

from .harness import (
    SseEventRecord,
    as_dict,
    as_str,
    override_app_runtime,
    poll_terminal,
    read_sse_events,
)
from .scenario_models import Scenario, load_scenarios

#: 真实模式唯一允许的场景与固定日期/轮询预算（真实 LLM + AMap 运行较慢）。
REAL_CASE_ID: Final = "happy_path"
REAL_EXPECTED_DATES: Final[tuple[str, str, str]] = ("2026-10-01", "2026-10-02", "2026-10-03")
REAL_POLL_TIMEOUT: Final = 600.0


class RealPreflightError(RuntimeError):
    """真实模式预检未通过。``problems`` 为缺失项清单（不含任何凭据值）。"""

    def __init__(self, problems: list[str]) -> None:
        self.problems: list[str] = list(problems)
        super().__init__("真实模式预检未通过: " + "; ".join(self.problems))


@dataclass(frozen=True)
class RealPreflight:
    """真实配置预检结果；``problems`` 为空即视为通过。"""

    problems: list[str]

    @property
    def ok(self) -> bool:
        return not self.problems


def preflight_real_config() -> RealPreflight:
    """检查真实运行所需的最小配置：LLM Key、高德 Key、``uvx`` 可执行。"""
    settings = get_settings()
    problems: list[str] = []
    if not (settings.openai_api_key or os.getenv("LLM_API_KEY")):
        problems.append("未配置 LLM Key（OPENAI_API_KEY 或 LLM_API_KEY）")
    if not settings.amap_api_key:
        problems.append("未配置高德 AMAP_API_KEY")
    if shutil.which("uvx") is None:
        problems.append("未找到 uvx（真实 AMap 经 uvx 启动 amap-mcp-server）")
    return RealPreflight(problems=problems)


def happy_path_scenario() -> Scenario:
    """返回 happy_path 黄金场景（真实模式只复用它声明的请求载荷）。"""
    for scenario in load_scenarios():
        if scenario.id == REAL_CASE_ID:
            return scenario
    raise RuntimeError(f"缺少黄金场景 {REAL_CASE_ID!r}")


@dataclass(frozen=True)
class RealHappyPathOutcome:
    """真实快乐路径的 HTTP 观测结果（结构校验输入）。"""

    http_status: int
    run_id: str
    terminal: dict[str, object]
    events: list[SseEventRecord]
    sse_content_type: str


def run_real_happy_path() -> RealHappyPathOutcome:
    """预检后经公开 HTTP 缝跑一次真实快乐路径；预检失败抛 :class:`RealPreflightError`。"""
    preflight = preflight_real_config()
    if not preflight.ok:
        raise RealPreflightError(preflight.problems)
    payload = dict(happy_path_scenario().request)
    runtime = AppRuntime.default()
    try:
        with override_app_runtime(runtime):
            with TestClient(app) as client:
                response = client.post("/api/trip/plan", json=payload)
                if response.status_code != 202:
                    raise AssertionError(f"真实模式受理失败: HTTP {response.status_code}")
                acceptance = as_dict(response.json())
                run_id = as_str(acceptance, "run_id")
                terminal = poll_terminal(client, run_id, timeout=REAL_POLL_TIMEOUT)
                events, content_type = read_sse_events(client, run_id)
                return RealHappyPathOutcome(
                    http_status=response.status_code,
                    run_id=run_id,
                    terminal=terminal,
                    events=events,
                    sse_content_type=content_type,
                )
    finally:
        runtime.close()


def validate_real_happy_path(outcome: RealHappyPathOutcome) -> None:
    """结构校验"上海 3 天 success"；坐标只验证存在且为数值，不比较桩的具体值。"""
    terminal = outcome.terminal
    assert as_str(terminal, "status") == "success", "真实快乐路径终态必须为 success"
    assert terminal.get("warnings") == [], (
        f"真实快乐路径不得携带降级告警，实际 {terminal.get('warnings')!r}"
    )
    result_value = terminal.get("result")
    assert isinstance(result_value, dict), "终态必须携带计划结果"
    result = result_value
    assert as_str(result, "city") == "上海", "计划城市必须为上海"

    days_value = result.get("days")
    assert isinstance(days_value, list), "计划 days 必须是列表"
    assert len(days_value) == 3, f"计划必须恰好 3 天，实际 {len(days_value)}"
    for index, day_value in enumerate(days_value):
        assert isinstance(day_value, dict), "day 必须是对象"
        assert as_str(day_value, "date") == REAL_EXPECTED_DATES[index], (
            "每日日期必须按 2026-10-01..03 递增"
        )
        assert day_value.get("day_index") == index, "day_index 必须与日期顺序一致"
        assert day_value.get("meals"), "每天必须包含餐饮"
        hotel = day_value.get("hotel")
        assert isinstance(hotel, dict) and hotel.get("name"), "每天必须推荐酒店"
        attractions_value = day_value.get("attractions")
        assert isinstance(attractions_value, list) and attractions_value, "每天必须包含景点"
        for attraction in attractions_value:
            assert isinstance(attraction, dict), "景点必须是对象"
            location = attraction.get("location")
            assert isinstance(location, dict), "景点必须携带坐标"
            lon = location.get("longitude")
            lat = location.get("latitude")
            assert isinstance(lon, (int, float)) and isinstance(lat, (int, float)), (
                "坐标必须为数值（不比较具体值）"
            )

    weather_value = result.get("weather_info")
    assert isinstance(weather_value, list) and weather_value, "必须包含天气信息"
    budget = result.get("budget")
    assert isinstance(budget, dict) and isinstance(budget.get("total"), (int, float)), "必须包含预算"
    assert result.get("overall_suggestions"), "必须包含总体建议"
    _assert_sse_contract(outcome)


def _assert_sse_contract(outcome: RealHappyPathOutcome) -> None:
    """基础 SSE 契约：内容类型 / run_id 一致 / 首 run_started、末 run_completed。"""
    assert outcome.sse_content_type == "text/event-stream", (
        f"SSE 内容类型应为 text/event-stream，实际 {outcome.sse_content_type!r}"
    )
    events = outcome.events
    assert events, "真实模式必须收到 SSE 事件流"
    types = [event.type for event in events]
    assert types[0] == "run_started", f"首事件必须是 run_started，实际 {types}"
    assert types[-1] == "run_completed", f"末事件必须是 run_completed，实际 {types}"
    assert all(event.run_id == outcome.run_id for event in events), "事件 run_id 必须与受理一致"
    completed = events[-1].data
    assert completed.get("status") == as_str(outcome.terminal, "status"), "SSE 终态与 GET 必须一致"