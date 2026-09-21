"""Run 后台执行器：受理与执行分离，执行结果写回注册表，事件推入 Run 通道。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

from loguru import logger

from ..models.schemas import TripPlan, TripRequest
from .events import RunEvent, RunEventType
from .models import RunStatus
from .registry import RunRegistry


class RunRunner:
    """在后台执行一次 Run，发布真实进度事件，并把终态与结果写回注册表。

    依赖经构造注入（factory），因此测试可用桩工厂替换整个执行链。
    SimpleAgent.run() 是同步阻塞调用，用独立的有界线程池（planner_executor）
    移出事件循环；事件发布从工作线程经线程安全通道送达 SSE 订阅者。
    """

    def __init__(
        self,
        factory: Any,
        registry: RunRegistry,
        planner_executor_provider: Optional[Callable[[], ThreadPoolExecutor]] = None,
    ) -> None:
        self.factory = factory
        self.registry = registry
        self._planner_executor_provider = planner_executor_provider

    def _publish(self, run_id: str, event_type: RunEventType, data: dict) -> None:
        """发布一条 Run 事件到注册表通道。"""
        self.registry.publish(run_id, RunEvent(run_id=run_id, type=event_type, data=data))

    def _make_sink(self, run_id: str):
        """构造事件发布函数（event_type, data）-> None，注入工厂/编排器。"""

        def sink(event_type: str, data: dict) -> None:
            try:
                self._publish(run_id, RunEventType(event_type), data)
            except ValueError:
                logger.warning("run_id={} 忽略未知事件类型 event_type={}", run_id, event_type)

        return sink

    def _build_planner_and_plan(self, run_id: str, request: TripRequest) -> TripPlan:
        """构造编排器并执行规划：均为同步阻塞操作，合并进同一工作线程。

        ``create_planner`` 可能拉起高德 MCP 子进程（秒级阻塞），必须与 ``plan_trip``
        一起经工作线程移出事件循环；否则构造期间的冻结会阻塞其他请求
        的受理与 SSE 心跳。构造失败与执行失败在此同样抛出，由 run() 统一落 failed。
        """
        planner = self.factory.create_planner(event_sink=self._make_sink(run_id))
        return planner.plan_trip(request)

    async def run(self, run_id: str, request: TripRequest) -> None:
        """执行 Run：running -> success | degraded | failed，全程发布真实事件。"""
        self.registry.transition(run_id, RunStatus.running)
        self._publish(run_id, RunEventType.run_started, {
            "status": RunStatus.running.value,
            "city": request.city,
            "travel_days": request.travel_days,
        })
        logger.info("run_started run_id={} city={} days={}", run_id, request.city, request.travel_days)
        try:
            if self._planner_executor_provider is not None:
                loop = asyncio.get_running_loop()
                trip_plan = await loop.run_in_executor(
                    self._planner_executor_provider(), self._build_planner_and_plan, run_id, request
                )
            else:
                # 无注入线程池时回退到事件循环默认执行器（独立构造 RunRunner 的场景）
                trip_plan = await asyncio.to_thread(self._build_planner_and_plan, run_id, request)
            # 先落终态（保证并发 GET /runs/{id} 与 SSE 看到一致的终态），再发终态事件
            self.registry.transition(run_id, RunStatus.success, result=trip_plan)
            self._publish(run_id, RunEventType.run_completed, {
                "status": RunStatus.success.value,
                "warnings": [],
                "result": trip_plan.model_dump(),
            })
            logger.info("run_completed run_id={} status=success", run_id)
        except Exception as e:  # 依赖构造或执行失败 -> 显式 failed（不伪造成功）
            logger.error("run_failed run_id={} error={}", run_id, str(e))
            self.registry.transition(run_id, RunStatus.failed, error=str(e))
            self._publish(run_id, RunEventType.run_completed, {
                "status": RunStatus.failed.value,
                "warnings": [],
                "error": str(e),
            })
        finally:
            # 终态事件已入历史，此后不再有新事件；关闭通道唤醒所有 SSE 等待者
            self.registry.close_channel(run_id)
