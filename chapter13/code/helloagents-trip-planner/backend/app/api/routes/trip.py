"""旅行规划API路由：Run 受理契约（受理即返回 run_id，状态经查询端点获取）。"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from ...models.schemas import TripRequest
from ...runtime.factory import AppRuntime, get_app_runtime
from ...runtime.models import RunAcceptance, RunStatusResponse

router = APIRouter(prefix="/trip", tags=["旅行规划"])


@router.post(
    "/plan",
    response_model=RunAcceptance,
    status_code=status.HTTP_202_ACCEPTED,
    summary="受理旅行规划请求",
    description="立即受理请求并返回 run_id；计划在后台生成，通过 GET /trip/runs/{run_id} 查询进度",
)
async def plan_trip(
    request: TripRequest,
    runtime: AppRuntime = Depends(get_app_runtime),
):
    """
    受理旅行规划请求（不再长阻塞）。

    受理与执行分离：本端点立即返回受理结果与 run_id；
    实际的多智能体编排在后台执行，前端经状态查询端点获取真实进度。
    """
    run = runtime.registry.create(request)
    logger.info("run_accepted run_id={} city={} days={}", run.run_id, request.city, request.travel_days)
    asyncio.create_task(runtime.runner.run(run.run_id, request))

    return RunAcceptance(
        run_id=run.run_id,
        status=run.status,
        message="旅行计划已受理，请通过 GET /api/trip/runs/{run_id} 查询运行状态",
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
        error=run.error,
        created_at=run.created_at,
        updated_at=run.updated_at,
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

