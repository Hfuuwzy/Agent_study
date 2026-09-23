"""断言支持层：类型化 JSON 字段访问 + 受理场景共用的 SSE / 搜索子断言。

与 ``checks`` 分离：本模块只承载跨场景复用的机械件——JSON 载荷的类型化收窄
（可信边界读取）、SSE 契约（内容类型 / run_id 一致 / 事件顺序 / 终态与 GET 一致）、
以及搜索步骤计数等共享子断言。场景专属断言留在 ``checks``。

``checks.assert_scenario`` 是唯一的公开断言入口（测试与未来 CLI 共用）。
"""

from typing import Final

from .harness import ScenarioRun

#: 终态集合（与公开契约一致）。
TERMINAL_STATUSES: Final[tuple[str, ...]] = ("success", "degraded", "failed")


# --------------------------------------------------------------------------- #
# 类型化字段访问：在 JSON 载荷的可信边界处做显式收窄，避免后续 untyped 访问。
# --------------------------------------------------------------------------- #

def str_of(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise AssertionError(f"字段 {key} 应为字符串，实际 {value!r}")
    return value


def int_of(data: dict[str, object], key: str) -> int:
    value = data.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise AssertionError(f"字段 {key} 应为整数，实际 {value!r}")


def float_of(data: dict[str, object], key: str) -> float:
    value = data.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise AssertionError(f"字段 {key} 应为数值，实际 {value!r}")


def dict_of(data: dict[str, object], key: str) -> dict[str, object]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise AssertionError(f"字段 {key} 应为对象，实际 {value!r}")
    return value


def optional_dict_of(data: dict[str, object], key: str) -> dict[str, object] | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise AssertionError(f"字段 {key} 应为对象或 null，实际 {value!r}")
    return value


def str_list_of(data: dict[str, object], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AssertionError(f"字段 {key} 应为字符串列表，实际 {value!r}")
    return value


def dict_list_of(data: dict[str, object], key: str) -> list[dict[str, object]]:
    value = data.get(key)
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return [dict(item) for item in value]
    raise AssertionError(f"字段 {key} 应为对象列表，实际 {value!r}")


# --------------------------------------------------------------------------- #
# SSE 契约（受理场景通用）
# --------------------------------------------------------------------------- #

def assert_sse_contract(run: ScenarioRun) -> None:
    """断言公开 SSE 契约：内容类型 / run_id 一致 / 事件顺序 / 终态与 GET 严格一致。"""
    assert run.sse_content_type == "text/event-stream", (
        f"SSE 内容类型应为 text/event-stream，实际 {run.sse_content_type!r}"
    )
    events = run.events
    assert events, "受理场景必须返回 SSE 事件流"
    types = [event.type for event in events]
    assert types[0] == "run_started", f"首事件必须是 run_started，实际 {types}"
    assert types[-1] == "run_completed", f"末事件必须是唯一终态 run_completed，实际 {types}"
    completed_count = sum(1 for t in types if t == "run_completed")
    assert completed_count == 1, f"必须恰好一条终态 run_completed，实际 {completed_count}"
    first_step = next((i for i, t in enumerate(types) if t in ("step_started", "tool_call")), None)
    assert first_step is not None and first_step > 0, (
        f"run_started 必须先于任何 step/tool 事件，实际 {types}"
    )
    assert run.run_id is not None, "受理场景必须携带 run_id"
    for event in events:
        assert event.run_id == run.run_id, (
            f"事件 run_id 与受理不一致: {event.run_id!r} != {run.run_id!r}"
        )
    terminal = run.terminal
    assert terminal is not None, "受理场景必须存在终态"
    completed = events[-1].data
    assert str_of(completed, "status") == str_of(terminal, "status"), "SSE 终态状态与 GET 不一致"
    assert completed.get("warnings") == terminal.get("warnings"), "SSE 终态告警与 GET 不一致"
    assert completed.get("error") == terminal.get("error"), "SSE 终态错误与 GET 不一致"
    assert completed.get("result") == terminal.get("result"), "SSE 终态结果与 GET 不一致"


# --------------------------------------------------------------------------- #
# 共享子断言
# --------------------------------------------------------------------------- #

def require_terminal(run: ScenarioRun, expected_status: str) -> dict[str, object]:
    """取回终态响应体并断言其状态与预期一致且属于契约枚举。"""
    terminal = run.terminal
    assert terminal is not None, "受理场景必须存在终态"
    actual = str_of(terminal, "status")
    assert actual == expected_status, f"终态应为 {expected_status}，实际 {actual}"
    assert actual in TERMINAL_STATUSES, f"未知终态 {actual!r}"
    return terminal


def assert_searches_once(run: ScenarioRun) -> None:
    """三个搜索步骤各执行一次：天气 1 次，text_search 景点/酒店各 1 次。"""
    assert len(run.probe.weather.calls) == 1, "天气查询必须只执行一次"
    text_calls = run.probe.text_search.calls
    assert len(text_calls) == 2, f"text_search 应被景点/酒店两步各调用一次，实际 {len(text_calls)}"
    attraction = [c for c in text_calls if "历史文化" in str(c.get("keywords", ""))]
    hotel = [c for c in text_calls if "酒店" in str(c.get("keywords", ""))]
    assert len(attraction) == 1, "景点搜索必须只执行一次"
    assert len(hotel) == 1, "酒店搜索必须只执行一次"


def assert_execution_steps(run: ScenarioRun, expected: list[str]) -> None:
    """step_started 事件携带的 step 序列必须与真实编排顺序一致。"""
    steps = [str_of(event.data, "step") for event in run.events if event.type == "step_started"]
    assert steps == expected, f"step_started 顺序应为 {expected}，实际 {steps}"


def tool_call_counts(run: ScenarioRun) -> dict[str, int]:
    """按工具名统计 SSE 流中的实际工具执行次数（规划重试不得增加搜索次数）。"""
    counts: dict[str, int] = {}
    for event in run.events:
        if event.type != "tool_call":
            continue
        name = event.data.get("tool_name")
        if isinstance(name, str):
            counts[name] = counts.get(name, 0) + 1
    return counts