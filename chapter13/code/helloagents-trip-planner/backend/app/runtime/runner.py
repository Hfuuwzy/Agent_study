"""Run 后台执行器：受理与执行分离，执行结果写回注册表，事件推入 Run 通道。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

from loguru import logger

from ..models.schemas import PlanningOutcome, TripRequest
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
        """构造事件发布函数（event_type, data）-> None，注入工厂/编排器。

        事件既是 SSE 的公开契约，也是控制台诊断的一部分：此处把每条事件
        同步输出到 loguru（含工具调用参数与结果预览），使后端终端能够与前端
        SSE 渲染逐个步骤对照，而不必依赖抓包/浏览器。
        """

        def sink(event_type: str, data: dict) -> None:
            try:
                etype = RunEventType(event_type)
            except ValueError:
                logger.warning("run_id={} 忽略未知事件类型 event_type={}", run_id, event_type)
                return
            self._log_event(run_id, etype, data)
            self._publish(run_id, etype, data)

        return sink

    @staticmethod
    def _log_event(run_id: str, etype: RunEventType, data: dict) -> None:
        """把一条 Run 事件以 loguru 结构化日志输出到控制台（不写文件）。"""
        if etype is RunEventType.run_started:
            logger.info("event=run_started run_id={} city={} travel_days={}",
                        run_id, data.get("city"), data.get("travel_days"))
        elif etype is RunEventType.step_started:
            logger.info("event=step_started run_id={} step={} label={} city={}",
                        run_id, data.get("step"), data.get("label"), data.get("city"))
        elif etype is RunEventType.tool_call:
            logger.info("event=tool_call run_id={} tool={} params={}",
                        run_id, data.get("tool_name"), data.get("parameters"))
        elif etype is RunEventType.tool_result:
            if data.get("error"):
                logger.error("event=tool_result run_id={} tool={} error={}",
                             run_id, data.get("tool_name"), data.get("error"))
            else:
                preview = data.get("result_preview")
                logger.info("event=tool_result run_id={} tool={} result={}",
                            run_id, data.get("tool_name"), preview)
        elif etype is RunEventType.validation_error:
            logger.warning("event=validation_error run_id={} step={} label={} error={}",
                           run_id, data.get("step"), data.get("label"), data.get("error"))

    def _build_planner_and_plan(self, run_id: str, request: TripRequest) -> PlanningOutcome:
        """构造编排器并执行规划：均为同步阻塞操作，合并进同一工作线程。

        ``create_planner`` 可能拉起高德 MCP 子进程（秒级阻塞），必须与 ``plan_trip``
        一起经工作线程移出事件循环；否则构造期间的冻结会阻塞其他请求
        的受理与 SSE 心跳。构造失败与执行失败在此同样抛出，由 run() 统一落 failed。
        """
        planner = self.factory.create_planner(event_sink=self._make_sink(run_id))
        return planner.plan_trip(request, run_id=run_id)

    def _publish_terminal(self, run_id: str) -> None:
        """基于已提交的终态记录发布 run_completed（与 GET 状态查询严格一致）。

        事件载荷取自注册表中已落定的终态记录而非局部变量，保证并发读取
        （GET /runs/{id} 与 SSE）看到同一份终态：status / warnings / result / error。
        """
        record = self.registry.get(run_id)
        if record is None:
            return
        data: dict = {
            "status": record.status.value,
            "warnings": list(record.warnings),
        }
        if record.result is not None:
            data["result"] = record.result.model_dump()
        if record.error is not None:
            data["error"] = record.error
        self._publish(run_id, RunEventType.run_completed, data)
        logger.info("run_completed run_id={} status={}", run_id, record.status.value)

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
                outcome = await loop.run_in_executor(
                    self._planner_executor_provider(), self._build_planner_and_plan, run_id, request
                )
            else:
                # 无注入线程池时回退到事件循环默认执行器（独立构造 RunRunner 的场景）
                outcome = await asyncio.to_thread(self._build_planner_and_plan, run_id, request)
            # 先落终态（保证并发 GET /runs/{id} 与 SSE 看到一致的终态），再发终态事件
            status = RunStatus.success if not outcome.warnings else RunStatus.degraded
            self.registry.transition(run_id, status, result=outcome.plan, warnings=outcome.warnings)
            self._publish_terminal(run_id)
        except Exception as e:  # 依赖构造或执行失败 -> 显式 failed（不伪造成功）
            logger.error("run_failed run_id={} error={}", run_id, str(e))
            self.registry.transition(
                run_id, RunStatus.failed, error=str(e), warnings=[f"生成旅行计划失败: {e}"]
            )
            self._publish_terminal(run_id)
        finally:
            # 终态事件已入历史，此后不再有新事件；关闭通道唤醒所有 SSE 等待者
            self.registry.close_channel(run_id)
