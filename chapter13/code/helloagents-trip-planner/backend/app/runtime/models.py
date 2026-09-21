"""Run 生命周期模型：状态机、运行记录与对外契约响应。"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from ..models.schemas import TripPlan, TripRequest


class RunStatus(str, Enum):
    """Run 状态机（进程内，零落盘）。

    pending -> running -> success | degraded | failed
    """

    pending = "pending"
    running = "running"
    success = "success"
    degraded = "degraded"
    failed = "failed"


class RunRecord(BaseModel):
    """一次行程生成运行（Run）的记录。"""

    run_id: str = Field(..., description="唯一运行标识")
    status: RunStatus = Field(default=RunStatus.pending, description="当前状态")
    request: TripRequest = Field(..., description="受理的旅行请求")
    result: Optional[TripPlan] = Field(default=None, description="运行结果(终态时存在)")
    warnings: List[str] = Field(default_factory=list, description="降级/失败告警清单(per-run)")
    error: Optional[str] = Field(default=None, description="失败原因(仅 failed)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RunAcceptance(BaseModel):
    """POST /trip/plan 的受理响应：立即返回，不携带最终计划。"""

    run_id: str = Field(..., description="本次运行的唯一标识")
    status: RunStatus = Field(..., description="受理瞬间的状态(pending/running)")
    message: str = Field(default="", description="受理消息")


class RunStatusResponse(BaseModel):
    """GET /trip/runs/{run_id} 的状态查询响应。"""

    run_id: str = Field(..., description="运行标识")
    status: RunStatus = Field(..., description="当前状态")
    request: TripRequest = Field(..., description="本次运行的请求")
    result: Optional[TripPlan] = Field(default=None, description="运行结果(终态时存在)")
    warnings: List[str] = Field(default_factory=list, description="降级/失败告警清单(per-run)")
    error: Optional[str] = Field(default=None, description="失败原因(仅 failed)")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")
