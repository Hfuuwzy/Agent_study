"""场景专属断言：对照场景 JSON 的预期逐条验证一次运行。

``assert_scenario`` 是唯一公开断言入口（测试与未来评测 CLI 共用）——不抛异常即
PASS，抛 ``AssertionError``（消息即失败原因）即 FAIL。对受理场景先统一执行
``assert_support.assert_sse_contract``（内容类型 / run_id 一致 / 事件顺序 / 终态与
GET 一致），再按 ``expect.kind`` 穷尽路由到场景专属断言。

与 ``assert_support`` 分离：本模块只含五个场景各自的专属断言；类型化 JSON 访问、
SSE 契约与搜索计数等共享子断言在 ``assert_support``。
"""

import json
from typing import assert_never

from .assert_support import (
    assert_execution_steps,
    assert_searches_once,
    assert_sse_contract,
    dict_list_of,
    dict_of,
    float_of,
    int_of,
    optional_dict_of,
    require_terminal,
    str_list_of,
    str_of,
    tool_call_counts,
)
from .harness import ScenarioRun
from .scenario_models import ExpectAccepted, ExpectRejected

#: 上海真实经纬度范围（夹具中景点/酒店坐标必须落在此区间，杜绝假坐标）。
SHANGHAI_LON = (120.9, 122.2)
SHANGHAI_LAT = (30.6, 32.0)


def assert_scenario(run: ScenarioRun) -> None:
    """按场景预期断言一次运行；失败以 AssertionError 消息给出原因。"""
    expect = run.scenario.expect
    match expect:
        case ExpectRejected():
            _assert_request_rejected(run, expect)
        case ExpectAccepted():
            assert_sse_contract(run)
            _assert_accepted_by_kind(run, expect)
        case unreachable:
            assert_never(unreachable)


def _assert_accepted_by_kind(run: ScenarioRun, expect: ExpectAccepted) -> None:
    """按 expect.kind 穷尽路由到四个受理场景专属断言。"""
    match expect.kind:
        case "success_structure":
            _assert_success_structure(run, expect)
        case "degraded_empty_shell":
            _assert_degraded_empty_shell(run, expect)
        case "retry_exhausted_failed":
            _assert_retry_exhausted_failed(run, expect)
        case "degraded_isolation":
            _assert_degraded_isolation(run, expect)
        case unreachable:
            assert_never(unreachable)


# --------------------------------------------------------------------------- #
# 场景 2：缺日期字段 -> 请求层 422 拒绝
# --------------------------------------------------------------------------- #

def _assert_request_rejected(run: ScenarioRun, expect: ExpectRejected) -> None:
    assert run.http_status == expect.http_status, (
        f"HTTP 状态应为 {expect.http_status}，实际 {run.http_status}"
    )
    detail = run.validation_detail or []
    assert detail, "422 响应必须携带 detail 校验错误清单"
    matched = [err for err in detail if err.get("loc") == expect.loc]
    assert matched, f"缺少定位 {expect.loc} 的校验错误，实际 {detail}"
    error_type = matched[0].get("type")
    assert isinstance(error_type, str) and error_type in expect.error_types, (
        f"定位 {expect.loc} 的错误类型应为 {expect.error_types}，实际 {detail}"
    )
    assert run.acceptance is None and run.run_id is None, "请求层拒绝不得受理任何 Run"
    assert run.health_runs_total == 0, (
        f"非法请求不得改变健康检查 runs_total，实际 {run.health_runs_total}"
    )
    assert run.probe.llm.calls == 0, "请求层拒绝不得调用 LLM"
    assert run.probe.llm.recorded_queries == [], "请求层拒绝不得调用 LLM"
    assert run.probe.text_search.calls == [], "请求层拒绝不得调用搜索工具"
    assert run.probe.weather.calls == [], "请求层拒绝不得调用天气工具"


# --------------------------------------------------------------------------- #
# 场景 1：快乐路径（上海 3 天全流程 success + 图片未命中占位契约）
# --------------------------------------------------------------------------- #

def _assert_success_structure(run: ScenarioRun, expect: ExpectAccepted) -> None:
    terminal = require_terminal(run, expect.terminal_status)
    result = dict_of(terminal, "result")
    assert str_list_of(terminal, "warnings") == [], "success 终态不得携带降级告警"
    assert str_of(result, "city") == "上海", "计划城市必须与请求一致"
    assert str_of(result, "start_date") == "2026-10-01"
    assert str_of(result, "end_date") == "2026-10-03"

    days = dict_list_of(result, "days")
    expected_dates = ["2026-10-01", "2026-10-02", "2026-10-03"]
    assert len(days) == 3, f"计划必须恰好 3 天，实际 {len(days)}"
    for index, day in enumerate(days):
        assert str_of(day, "date") == expected_dates[index], f"第 {index + 1} 天日期错误"
        assert int_of(day, "day_index") == index, f"第 {index + 1} 天 day_index 错误"
        assert dict_list_of(day, "meals"), f"第 {index + 1} 天必须包含餐饮"
        hotel = optional_dict_of(day, "hotel")
        assert hotel is not None and str_of(hotel, "name") == "上海快捷酒店", "酒店必须来自夹具且正确"
        for attraction in dict_list_of(day, "attractions"):
            location = dict_of(attraction, "location")
            lon = float_of(location, "longitude")
            lat = float_of(location, "latitude")
            assert SHANGHAI_LON[0] <= lon <= SHANGHAI_LON[1], f"经度超出上海范围: {lon}"
            assert SHANGHAI_LAT[0] <= lat <= SHANGHAI_LAT[1], f"纬度超出上海范围: {lat}"

    assert len(dict_list_of(result, "weather_info")) == 3, "天气信息必须覆盖 3 天"
    budget = optional_dict_of(result, "budget")
    assert budget is not None and int_of(budget, "total") > 0, "success 终态必须包含预算"

    if expect.assert_photo_miss_contract:
        _assert_photo_miss_contract(run)
    if expect.searches_once:
        assert_searches_once(run)
        assert_execution_steps(run, ["attractions", "weather", "hotels", "plan"])
    expected_attempts = expect.planner_attempts or 1
    assert len(run.planner_queries) == expected_attempts, (
        f"快乐路径应恰好调用规划 Agent {expected_attempts} 次"
    )


def _assert_photo_miss_contract(run: ScenarioRun) -> None:
    photo = run.photo
    assert photo is not None, "场景必须经注入 Unsplash 桩记录图片查询结果"
    assert photo.get("is_placeholder") is True, f"未命中图片必须返回占位契约，实际 {photo}"
    assert photo.get("photo_url") is None, f"未命中不得返回非对应城市图片，实际 {photo}"
    assert photo.get("warnings"), f"未命中占位必须携带告警清单，实际 {photo}"
    assert run.probe.unsplash.calls, "桩 Unsplash 必须被实际调用"


# --------------------------------------------------------------------------- #
# 场景 3：搜索空结果 -> 诚实的 degraded 空壳
# --------------------------------------------------------------------------- #

def _assert_degraded_empty_shell(run: ScenarioRun, expect: ExpectAccepted) -> None:
    terminal = require_terminal(run, expect.terminal_status)
    result = dict_of(terminal, "result")
    warnings = str_list_of(terminal, "warnings")
    assert warnings, "degraded 终态必须携带告警清单"
    assert any("返回空结果" in w for w in warnings), f"告警应指出空结果，实际 {warnings}"
    assert dict_list_of(result, "days") == [], "诚实空壳的 days 必须为空"
    assert dict_list_of(result, "weather_info") == [], "诚实空壳的 weather_info 必须为空"
    assert optional_dict_of(result, "budget") is None, "诚实空壳的 budget 必须为 null"
    assert str_of(result, "overall_suggestions"), "诚实空壳必须保留总体建议文案"
    assert not run.planner_queries, "空搜索结果不得触发规划步骤"
    assert run.probe.weather.calls == [], "景点空结果后天气步骤不得执行"
    steps = [str_of(event.data, "step") for event in run.events if event.type == "step_started"]
    assert steps == ["attractions"], f"只应执行景点步骤，实际 {steps}"
    serialized = json.dumps(result, ensure_ascii=False)
    assert "longitude" not in serialized and "latitude" not in serialized, "空壳不得包含伪造坐标"


# --------------------------------------------------------------------------- #
# 场景 4：最终规划 schema 非法 -> 生产有界重试 3 次仍失败 -> 显式 failed
# --------------------------------------------------------------------------- #

def _assert_retry_exhausted_failed(run: ScenarioRun, expect: ExpectAccepted) -> None:
    terminal = require_terminal(run, expect.terminal_status)
    error = terminal.get("error")
    assert isinstance(error, str) and error, "failed 终态必须携带错误原因"
    assert terminal.get("result") is None, "failed 终态不得伪造计划结果"
    assert str_list_of(terminal, "warnings"), "failed 终态必须携带告警清单"
    assert len(run.planner_queries) == expect.planner_attempts, (
        f"规划 Agent 必须恰好尝试 {expect.planner_attempts} 次，"
        f"实际 {len(run.planner_queries)}"
    )
    if expect.searches_once:
        assert_searches_once(run)
    assert tool_call_counts(run) == {"amap_maps_text_search": 2, "amap_maps_weather": 1}, (
        "规划重试不得重复执行搜索工具"
    )


# --------------------------------------------------------------------------- #
# 场景 5：恶意输入隔离（用户/工具双哨兵均不进规划上下文，干净 POI 保留）
# --------------------------------------------------------------------------- #

def _assert_degraded_isolation(run: ScenarioRun, expect: ExpectAccepted) -> None:
    terminal = require_terminal(run, expect.terminal_status)
    warnings = str_list_of(terminal, "warnings")
    assert any("已隔离自由文本" in w for w in warnings), f"应标注自由文本隔离，实际 {warnings}"
    assert any("已隔离疑似注入的条目" in w for w in warnings), f"应标注工具条目隔离，实际 {warnings}"

    user_sentinel = run.scenario.stubs.user_sentinel
    tool_sentinel = run.scenario.stubs.tool_sentinel
    assert user_sentinel is not None, "degraded_isolation 场景必须配置 user_sentinel"
    assert tool_sentinel is not None, "degraded_isolation 场景必须配置 tool_sentinel"
    planner_queries = run.planner_queries
    assert planner_queries, "隔离后规划步骤仍应执行（干净数据照常生成计划）"
    for query in planner_queries:
        assert user_sentinel not in query, "用户哨兵不得进入规划提示词"
        assert tool_sentinel not in query, "工具哨兵不得进入规划提示词"
    assert "外滩" in planner_queries[0], "干净 POI 数据必须保留在规划上下文中"

    result = dict_of(terminal, "result")
    assert result.get("days"), "隔离后仍应产出真实计划"
    attraction_names = [
        str_of(attraction, "name")
        for day in dict_list_of(result, "days")
        for attraction in dict_list_of(day, "attractions")
    ]
    assert "外滩" in attraction_names, "干净 POI 必须出现在最终计划中"

    expected_attempts = expect.planner_attempts or 1
    assert len(run.planner_queries) == expected_attempts, (
        f"计划应恰好调用规划 Agent {expected_attempts} 次"
    )
    if expect.searches_once:
        assert_searches_once(run)
        assert_execution_steps(run, ["attractions", "weather", "hotels", "plan"])