"""Run 事件协议与进程内事件通道。

事件协议（向前的公开契约，SSE 载荷与前端类型镜像同一结构）：
    run_started / step_started / tool_call / tool_result / validation_error / run_completed

- ``run_started``      Run 进入 running 时发出；data 含 status/city/travel_days。
- ``step_started``     编排四步（景点/天气/酒店/计划）各自开始时发出；data 含 step/label。
- ``tool_call``        展开的高德工具被实际执行前发出；data 含 tool_name/parameters。
- ``tool_result``      工具执行完成后发出；data 含 tool_name 与 result_preview（或 error）。
- ``validation_error`` 中间结果或最终计划的 schema 校验失败时发出（由工单 04 生产，此处仅定义契约）。
- ``run_completed``    Run 到达终态时发出；data 含终态 status、warnings（成功/降级）与 error（失败）。

通道约定（ADR-0003）：事件只驻留进程内存，不落盘。每个 Run 一个通道，支持全量历史重放
（迟到订阅者直接收到完整事件序列）与实时追加（wait_next 阻塞等待）。线程安全：执行器
（工作线程）发布、SSE 端点（事件循环）读取。
"""

import threading
import time
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field


class RunEventType(str, Enum):
    """SSE 事件类型（协议公开枚举）。"""

    run_started = "run_started"
    step_started = "step_started"
    tool_call = "tool_call"
    tool_result = "tool_result"
    validation_error = "validation_error"
    run_completed = "run_completed"


class RunEvent(BaseModel):
    """一条 Run 事件：run_id + 类型 + 载荷 + 时间戳。"""

    run_id: str = Field(..., description="所属运行标识")
    type: RunEventType = Field(..., description="事件类型")
    data: dict = Field(default_factory=dict, description="事件载荷（按类型约定）")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RunEventChannel:
    """单个 Run 的事件通道：发布订阅 + 全量历史重放，线程安全，进程内零落盘。

    约定：
    - ``publish`` 追加事件并唤醒所有等待者；
    - ``close`` 标记通道关闭并唤醒等待者（终态事件已随最后一次 publish 进入历史，
      关闭只表示"不再有新事件"）；
    - ``snapshot`` 返回全量历史（迟到订阅者重放用）；
    - ``wait_next`` 从 ``from_index`` 起阻塞等待新事件，返回 (新事件列表, 是否已关闭)。
    """

    def __init__(self) -> None:
        self._events: List[RunEvent] = []
        self._closed = False
        self._cond = threading.Condition()

    def publish(self, event: RunEvent) -> None:
        """追加一条事件并唤醒等待者。"""
        with self._cond:
            self._events.append(event)
            self._cond.notify_all()

    def close(self) -> None:
        """关闭通道：后续 publish 不再有意义（调用方须保证先发布完终态事件）。"""
        with self._cond:
            self._closed = True
            self._cond.notify_all()

    def snapshot(self) -> List[RunEvent]:
        """返回当前全量历史事件（线程安全快照）。"""
        with self._cond:
            return list(self._events)

    @property
    def closed(self) -> bool:
        with self._cond:
            return self._closed

    def wait_next(self, from_index: int, timeout: Optional[float] = None) -> Tuple[List[RunEvent], bool]:
        """从 from_index 起等待新事件。

        Args:
            from_index: 已消费事件数（下一条的索引）。
            timeout: 总超时预算秒数；空闲达到预算后返回 ([], False)，由调用方
                决定重试或保活（SSE 心跳依赖该返回，而非无限阻塞）。

        Returns:
            (新事件列表, 通道是否已关闭)。关闭时立即返回；空闲超时返回 ([], False)。
        """
        with self._cond:
            deadline = None if timeout is None else time.monotonic() + timeout
            while len(self._events) <= from_index and not self._closed:
                if deadline is None:
                    self._cond.wait()
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return [], self._closed
                    self._cond.wait(timeout=remaining)
            return list(self._events[from_index:]), self._closed
