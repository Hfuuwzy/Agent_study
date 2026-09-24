"""景点 / 天气 / 酒店搜索步骤的单步有界重试。

与 ``final_plan_retry`` 同策略：总尝试上限 3 次、指数退避 ``0.1s -> 0.2s``
（``0.1 * 2^(n-1)``）。区别在失败语义：

- 最终规划（``final_plan_retry``）重试耗尽抛 ``FinalPlanError``，由 runner 落 ``failed``；
- 搜索步骤重试耗尽保持现有**显式降级**语义：返回 ``(None, warnings)``，由编排器
  ``plan_trip`` 落 ``degraded``（空壳计划，不伪造成功）。

重试边界（spec 第 14/47 行）：只重试失败的那一步，已完成的搜索步骤与已固化的
类型化中间结果绝不因后续重试而重跑。``attempt`` 由编排器注入，包住"单次 Agent 运行
+ 失败证据取回 + 结果取回 + 类型化解析"的完整一跳；每次尝试都会 drain 取回并清空
录制器，避免把上一次尝试的陈旧结果误当作本次成功。

``sleep`` 可注入，供单元测试以记录桩验证退避序列而不消耗真实时间。
"""

import time
from collections.abc import Callable, Sequence
from typing import Final, TypeVar

_T = TypeVar("_T")

#: 单个搜索步骤的总尝试次数上限（含首次）。与最终规划保持一致（spec 未给数值，取父决策）。
SEARCH_STEP_MAX_ATTEMPTS: Final = 3

#: 重试间退避延迟（秒）：指数退避，第 n 次重试前等待 ``0.1 * 2**n``（n 从 0 起）。
SEARCH_STEP_BACKOFF: Final[tuple[float, ...]] = (0.1, 0.2)


def retry_search_step(
    attempt: Callable[[], tuple[_T | None, list[str], dict | None]],
    *,
    max_attempts: int = SEARCH_STEP_MAX_ATTEMPTS,
    backoff: Sequence[float] = SEARCH_STEP_BACKOFF,
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Callable[[int, float], None] | None = None,
) -> tuple[_T | None, list[str], int, dict | None]:
    """有界重试单个搜索步骤的一次完整尝试。

    Args:
        attempt: 执行一次完整的步骤尝试。返回 ``(typed, warnings, validation_error)``：
            - ``typed``: 类型化中间结果；``None`` 表示本次尝试失败（可重试）。
            - ``warnings``: 本次尝试内累积的失败证据（工具失败 / 结果缺失 / 校验失败）。
            - ``validation_error``: 若是 schema-校验 / 空结果类失败，返回事件载荷
              ``{"step", "label", "error"}`` 供编排器在**步骤最终耗尽**时发一次
              ``validation_error``；否则为 ``None``。
        max_attempts: 总尝试次数上限（含首次），默认 3。
        backoff: 重试间等待的秒数序列，按失败次数依次取用；耗尽后沿用末位。
        sleep: 等待函数（默认 ``time.sleep``）。可注入为记录桩，使测试能验证退避
            序列而不消耗真实时间；不经 HTTP 契约暴露。
        on_retry: 可选回调，在第 ``next_attempt`` 次尝试前的退避等待之前调用，
            参数为 (next_attempt, delay)，供编排器记录"正在重试"日志。

    Returns:
        ``(typed, all_warnings, attempts, final_validation_error)``：
        - 成功：``typed`` 非 None，``attempts`` 为实际尝试次数，``final_validation_error`` 为 None；
        - 耗尽：``typed`` 为 None，``attempts`` 为 ``max_attempts``，
          ``final_validation_error`` 为最后一次失败的事件载荷（非校验类失败则为 None）。
    """
    all_warnings: list[str] = []
    final_validation_error: dict | None = None
    for attempt_no in range(1, max_attempts + 1):
        if attempt_no > 1 and backoff:
            delay = backoff[min(attempt_no - 2, len(backoff) - 1)]
            if on_retry is not None:
                on_retry(attempt_no, delay)
            sleep(delay)
        try:
            typed, warnings, validation_error = attempt()
        except Exception as error:
            typed = None
            warnings = [f"搜索步骤执行失败: {type(error).__name__}: {error}"]
            validation_error = None
        all_warnings += warnings
        final_validation_error = validation_error
        if typed is not None:
            return typed, all_warnings, attempt_no, None
    return None, all_warnings, max_attempts, final_validation_error