"""Run 内存注册表：进程内、零落盘、线程安全。"""

import threading
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from ..models.schemas import TripPlan, TripRequest
from .models import RunRecord, RunStatus


class RunRegistry:
    """按 run_id 存取的进程内 Run 注册表。

    约定（ADR-0003）：状态仅存内存，进程退出即丢失；不写数据库、不写日志文件。
    多个 worker 进程各自持有独立注册表，同一 run 只应由受理它的进程执行与查询。
    """

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._lock = threading.Lock()

    def create(self, request: TripRequest) -> RunRecord:
        """受理一个新 Run，初始状态为 pending。"""
        run = RunRecord(run_id=uuid4().hex, status=RunStatus.pending, request=request)
        with self._lock:
            self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> Optional[RunRecord]:
        """按 run_id 查询 Run；不存在时返回 None。"""
        with self._lock:
            return self._runs.get(run_id)

    def transition(
        self,
        run_id: str,
        status: RunStatus,
        result: Optional[TripPlan] = None,
        error: Optional[str] = None,
    ) -> RunRecord:
        """推进 Run 到新状态，可附带结果或错误；Run 不存在时抛 KeyError。"""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(f"Run {run_id} 不存在")
            run.status = status
            if result is not None:
                run.result = result
            if error is not None:
                run.error = error
            run.updated_at = datetime.now(timezone.utc)
            return run

    def __len__(self) -> int:
        with self._lock:
            return len(self._runs)
