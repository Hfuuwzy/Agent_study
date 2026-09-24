"""最终规划步骤的有界重试：规划响应解析/校验失败时最多重试 3 次。

工单 06（评测集样例 4）：模型输出 schema 非法，经有界重试仍失败时，由 runner
显式落 ``failed``（不伪造成功）。本模块把"最终规划最多尝试 N 次"这一窄职责从
``trip_planner_agent`` 剥离：编排器只负责组织流水线，重试语义集中于此。

重试边界：只重试"规划响应无法解析 / 无法校验为 TripPlan"这一类失败；三个搜索
步骤已在此前完成并固化为类型化中间结果，不属于重试范围，不会被再次执行。

退避策略（spec 第 14/47 行：指数退避）：3 次总尝试间延迟 0.1s -> 0.2s，
即 ``0.1 * 2^(n-1)``。生产路径经 ``time.sleep`` 真实等待；``sleep`` 可注入，
供单元测试以记录桩验证延迟序列而不消耗真实时间。
"""

import time
from collections.abc import Callable, Sequence
from typing import Final

from ..models.schemas import TripPlan

#: 最终规划的总尝试次数上限（含首次）。规范只要求"有界"，父决策取 3。
FINAL_PLAN_MAX_ATTEMPTS: Final = 3

#: 重试间的退避延迟（秒）：指数退避，第 n 次重试前等待 ``0.1 * 2**(n-1)``。
FINAL_PLAN_BACKOFF: Final[tuple[float, ...]] = (0.1, 0.2)


class FinalPlanError(RuntimeError):
    """最终规划在尝试上限内均未产出可解析、可校验为 TripPlan 的响应。

    携带 ``attempts``（已尝试次数）与 ``last_error``（最后一次失败原因），
    供 runner 如实写入终态 error / warnings。
    """

    def __init__(self, attempts: int, last_error: str) -> None:
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"行程规划响应解析失败（已尝试 {attempts} 次）: {last_error}")


def plan_final_with_retry(
    run: Callable[[], str],
    parse: Callable[[str], TripPlan],
    *,
    max_attempts: int = FINAL_PLAN_MAX_ATTEMPTS,
    backoff: Sequence[float] = FINAL_PLAN_BACKOFF,
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Callable[[int, float], None] | None = None,
) -> TripPlan:
    """有界重试最终规划步骤：响应不可解析/不可校验为 TripPlan 时重新运行规划器。

    Args:
        run: 执行一次最终规划器；每次调用即一次完整的规划器运行（调用次数
            即规划器总运行次数，重试不会重跑任何搜索步骤）。
        parse: 把单次响应解析为 TripPlan；解析或 schema 校验失败抛 ``ValueError``。
            JSON 解码失败（``json.JSONDecodeError``）、Pydantic ``ValidationError``
            与"响应中未找到 JSON"均是其子类，故统一按 ``ValueError`` 处理。
        max_attempts: 总尝试次数上限（含首次），默认 3。
        backoff: 重试间等待的秒数序列，按失败次数依次取用；耗尽后沿用末位。
        sleep: 等待函数（默认 ``time.sleep``）。可注入为记录桩，使测试能验证
            退避序列而不消耗真实时间；不经 HTTP 契约暴露。
        on_retry: 可选回调，在第 ``attempt`` 次尝试前的退避等待之前调用，参数为
            ``(attempt, delay)``，供调用方记录重试诊断；不改变重试语义。

    Raises:
        FinalPlanError: 连续 ``max_attempts`` 次失败（携带最后一次失败原因）。
    """
    last_error = "未执行任何尝试"
    for attempt in range(1, max_attempts + 1):
        if attempt > 1 and backoff:
            delay = backoff[min(attempt - 2, len(backoff) - 1)]
            if on_retry is not None:
                on_retry(attempt, delay)
            sleep(delay)
        response = run()
        try:
            return parse(response)
        except ValueError as error:
            last_error = str(error)
    raise FinalPlanError(max_attempts, last_error)
