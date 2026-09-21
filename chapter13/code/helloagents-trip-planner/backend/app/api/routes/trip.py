"""旅行规划API路由：Run 受理契约 + 状态查询 + SSE 真实进度事件流。"""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from loguru import logger

from ...models.schemas import TripRequest
from ...runtime.events import RunEvent
from ...runtime.factory import AppRuntime, get_app_runtime
from ...runtime.models import RunAcceptance, RunStatusResponse

router = APIRouter(prefix="/trip", tags=["旅行规划"])

#: SSE 无新事件时的保活心跳间隔（秒）；窗口内无事件则发一条注释行维持连接。
SSE_HEARTBEAT_SECONDS = 10.0


def _format_sse(event: RunEvent) -> str:
    """把一条 Run 事件序列化为 SSE 帧（event + data，data 为完整 JSON 载荷）。"""
    payload = json.dumps(
        {
            "run_id": event.run_id,
            "type": event.type.value,
            "data": event.data,
            "timestamp": event.timestamp.isoformat(),
        },
        ensure_ascii=False,
    )
    return f"event: {event.type.value}\ndata: {payload}\n\n"


@router.post(
    "/plan",
    response_model=RunAcceptance,
    status_code=status.HTTP_202_ACCEPTED,
    summary="受理旅行规划请求",
    description="立即受理请求并返回 run_id；计划在后台生成，通过 GET /trip/runs/{run_id} 查询进度，"
    "或经 GET /trip/runs/{run_id}/events 订阅 SSE 真实进度事件流",
)
async def plan_trip(
    request: TripRequest,
    runtime: AppRuntime = Depends(get_app_runtime),
):
    """
    受理旅行规划请求（不再长阻塞）。

    受理与执行分离：本端点立即返回受理结果与 run_id；
    实际的多智能体编排在后台执行，前端经 SSE 事件流或状态查询端点获取真实进度。
    """
    run = runtime.registry.create(request)
    logger.info("run_accepted run_id={} city={} days={}", run.run_id, request.city, request.travel_days)
    asyncio.create_task(runtime.runner.run(run.run_id, request))

    return RunAcceptance(
        run_id=run.run_id,
        status=run.status,
        message="旅行计划已受理，可通过 GET /api/trip/runs/{run_id}/events 订阅 SSE 事件流，"
        "或 GET /api/trip/runs/{run_id} 查询运行状态",
    )


@router.get(
    "/runs/{run_id}",
    response_model=RunStatusResponse,
    summary="查询运行状态",
    description="按 run_id 查询一次运行的状态（pending/running/success/degraded/failed）与结果",
)
async def get_run_status(
    run_id: str,
    runtime: AppRuntime = Depends(get_app_runtime),
):
    """查询 Run 状态。"""
    run = runtime.registry.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} 不存在")
    return RunStatusResponse(
        run_id=run.run_id,
        status=run.status,
        request=run.request,
        result=run.result,
        warnings=list(run.warnings),
        error=run.error,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.get(
    "/runs/{run_id}/events",
    summary="订阅运行进度事件流（SSE）",
    description="以 Server-Sent Events 推送该 Run 的真实进度：run_started / step_started / "
    "tool_call / tool_result / validation_error / run_completed。终态事件 run_completed 携带 "
    "status（success/degraded/failed）。迟到订阅者会先收到全量历史重放，再进入实时流。",
)
async def stream_run_events(
    run_id: str,
    runtime: AppRuntime = Depends(get_app_runtime),
):
    """SSE 事件流：历史重放 + 实时追加，无新事件时心跳保活，终态后自动结束。"""
    run = runtime.registry.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} 不存在")
    channel = runtime.registry.channel(run_id)
    if channel is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} 的事件通道不存在")

    async def event_stream():
        # 1) 全量历史重放：迟到订阅/断线重连都能拿到一致的事件序列
        snapshot = channel.snapshot()
        seen = len(snapshot)
        for event in snapshot:
            yield _format_sse(event)
        # 2) 实时追加：阻塞等待新事件（经 SSE 专用线程池不阻塞事件循环），心跳保活
        loop = asyncio.get_running_loop()
        sse_executor = runtime.sse_executor()
        while True:
            new_events, closed = await loop.run_in_executor(
                sse_executor, channel.wait_next, seen, SSE_HEARTBEAT_SECONDS
            )
            for event in new_events:
                seen += 1
                yield _format_sse(event)
            if closed:
                logger.info("sse_stream_end run_id={} events={}", run_id, seen)
                break
            yield ": keepalive\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/health",
    summary="健康检查",
    description="检查旅行规划服务是否正常（不触发任何外部依赖构造）",
)
async def health_check(runtime: AppRuntime = Depends(get_app_runtime)):
    """健康检查：只读取进程内状态，不构造 Agent（避免健康检查触发 MCP 子进程）。"""
    return {
        "status": "healthy",
        "service": "trip-planner",
        "runs_total": len(runtime.registry),
        "runtime_factory": type(runtime.factory).__name__,
    }

