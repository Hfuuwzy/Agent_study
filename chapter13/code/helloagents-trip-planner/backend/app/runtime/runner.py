"""Run 后台执行器：受理与执行分离，执行结果写回注册表。"""

import asyncio
from typing import Any

from loguru import logger

from ..models.schemas import TripRequest
from .models import RunStatus
from .registry import RunRegistry


class RunRunner:
    """在后台执行一次 Run，并把终态与结果写回注册表。

    依赖经构造注入（factory），因此测试可用桩工厂替换整个执行链。
    SimpleAgent.run() 是同步阻塞调用，用 asyncio.to_thread 移出事件循环。
    """

    def __init__(self, factory: Any, registry: RunRegistry) -> None:
        self.factory = factory
        self.registry = registry

    async def run(self, run_id: str, request: TripRequest) -> None:
        """执行 Run：running -> success | degraded | failed。"""
        self.registry.transition(run_id, RunStatus.running)
        logger.info("run_started run_id={} city={} days={}", run_id, request.city, request.travel_days)
        try:
            planner = self.factory.create_planner()
            trip_plan = await asyncio.to_thread(planner.plan_trip, request)
            self.registry.transition(run_id, RunStatus.success, result=trip_plan)
            logger.info("run_completed run_id={} status=success", run_id)
        except Exception as e:  # 依赖构造或执行失败 -> 显式 failed（不伪造成功）
            logger.error("run_failed run_id={} error={}", run_id, str(e))
            self.registry.transition(run_id, RunStatus.failed, error=str(e))