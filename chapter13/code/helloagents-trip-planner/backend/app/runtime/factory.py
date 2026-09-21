"""运行时工厂与依赖注入。

将进程级全局单例（LLM / 高德 MCP / Unsplash / 编排器）替换为按需构造的工厂：
- 生产路径：``RuntimeFactory.from_settings()`` 在应用启动时构建一次，依赖在首次使用时惰性构造
  （高德 MCPTool 在本工厂内共享，避免每个 Run 拉起一个 MCP 子进程；语义与"共享单例"一致，
  但归属从模块全局移到容器实例，可整体替换）。
- 测试路径：直接以桩工厂构造 ``RuntimeFactory(llm_factory=..., amap_tool_factory=..., unsplash_factory=...)``，
  并经 ``get_app_runtime`` 的 dependency_overrides 注入 —— 测试缝 = 公开 HTTP API。

线程模型（评审修复）：规划构造/执行与 SSE 空闲等待分属不同执行器。
``AppRuntime.sse_executor()`` 提供独立的有界线程池给 SSE 等待，避免长时间空闲的
订阅者占用默认执行器容量、拖慢后续 Run 的受理与执行；``close()`` 在应用关闭时回收。
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException, Request

from .. import config as _config  # noqa: F401  # 保证 load_dotenv() 先于 hello_agents 导入
from ..agents.trip_planner_agent import MultiAgentTripPlanner
from ..services.amap_service import AmapService, create_amap_mcp_tool
from ..services.llm_service import create_llm
from ..services.unsplash_service import UnsplashService, create_unsplash
from .probe import EventEmittingAmapTool
from .registry import RunRegistry
from .runner import RunRunner

# 仅用于类型注解
HelloAgentsLLM = Any
MCPTool = Any


class RuntimeFactory:
    """按需构造运行时对象的工厂；LLM / 高德 MCP / Unsplash 均经注入点进入。"""

    def __init__(
        self,
        llm_factory: Callable[[], Any],
        amap_tool_factory: Callable[[], Any],
        unsplash_factory: Callable[[], Any],
    ) -> None:
        self._llm_factory = llm_factory
        self._amap_tool_factory = amap_tool_factory
        self._unsplash_factory = unsplash_factory

    def create_llm(self) -> Any:
        """构造 LLM 实例（真实 HelloAgentsLLM 或测试桩）。"""
        return self._llm_factory()

    def create_amap_tool(self) -> Any:
        """构造高德 MCP 工具（真实 MCPTool 或测试桩）。"""
        return self._amap_tool_factory()

    def create_unsplash(self) -> Any:
        """构造 Unsplash 服务（真实 UnsplashService 或测试桩）。"""
        return self._unsplash_factory()

    def create_planner(self, event_sink: Optional[Callable[[str, dict], None]] = None) -> MultiAgentTripPlanner:
        """按 Run 构造编排器：LLM 与高德工具均为本次运行的独立组合。

        Args:
            event_sink: 可选的事件发布函数 (event_type, data) -> None。
                提供时，高德工具被事件探针包装，工具实际执行会发出 tool_call / tool_result
                事件（SSE 真实进度）；编排器四步各发 step_started。不提供则保持无事件行为。
        """
        amap_tool = self.create_amap_tool()
        if event_sink is not None:
            amap_tool = EventEmittingAmapTool(amap_tool, event_sink)
        return MultiAgentTripPlanner(
            llm=self.create_llm(),
            amap_tool=amap_tool,
            event_sink=event_sink,
        )

    def create_amap_service(self) -> AmapService:
        """构造手动地图服务（POI/天气/路线路由使用）。"""
        return AmapService(mcp_tool=self.create_amap_tool())

    @classmethod
    def from_settings(cls, settings: Optional[Any] = None) -> "RuntimeFactory":
        """生产默认：从 Settings 构造；MCP 工具在本工厂内惰性共享（避免重复拉起子进程）。"""
        s = settings if settings is not None else _config.get_settings()
        amap_cache: Dict[str, Any] = {}

        def build_amap_tool() -> Any:
            if "tool" not in amap_cache:
                amap_cache["tool"] = create_amap_mcp_tool(s)
            return amap_cache["tool"]

        return cls(
            llm_factory=create_llm,
            amap_tool_factory=build_amap_tool,
            unsplash_factory=lambda: create_unsplash(s),
        )


class AppRuntime:
    """应用级运行时容器：工厂 + Run 注册表 + 后台执行器，随应用启动构建。

    规划与 SSE 各使用独立的有界线程池（``planner_executor`` / ``sse_executor``），
    互不抢占：长时间空闲的 SSE 订阅者不会拖慢后续 Run 的构造/执行，反之亦然。
    两者均按需惰性创建，``close`` 在应用关闭时统一回收。
    """

    def __init__(
        self,
        factory: RuntimeFactory,
        registry: Optional[RunRegistry] = None,
        runner: Optional[RunRunner] = None,
        planner_max_workers: int = 4,
        sse_max_workers: int = 4,
    ) -> None:
        self.factory = factory
        self.registry = registry if registry is not None else RunRegistry()
        self.runner = runner if runner is not None else RunRunner(
            factory=factory, registry=self.registry, planner_executor_provider=self.planner_executor
        )
        self._planner_max_workers = planner_max_workers
        self._sse_max_workers = sse_max_workers
        self._planner_executor: Optional[ThreadPoolExecutor] = None
        self._sse_executor: Optional[ThreadPoolExecutor] = None
        self._executor_lock = Lock()

    @classmethod
    def default(cls) -> "AppRuntime":
        """生产默认容器：真实依赖惰性构造。"""
        factory = RuntimeFactory.from_settings()
        return cls(factory=factory)

    def planner_executor(self) -> ThreadPoolExecutor:
        """构造并执行规划所用的专用线程池。

        规划（create_planner + plan_trip）是秒级同步阻塞调用；独立的池保证其容量
        不被 SSE 空闲等待挤占，同时有界上限避免无限并发阻塞。
        """
        if self._planner_executor is None:
            with self._executor_lock:
                if self._planner_executor is None:
                    self._planner_executor = ThreadPoolExecutor(
                        max_workers=self._planner_max_workers,
                        thread_name_prefix="planner",
                    )
        return self._planner_executor

    def sse_executor(self) -> ThreadPoolExecutor:
        """SSE 空闲等待专用的有界线程池（线程安全惰性创建）。

        每个空闲 SSE 订阅者在等待下一批事件时占用一名工作线程（非阻塞事件循环），
        与规划线程池隔离；超出的并发订阅者排队等待空闲线程，而不是挤占规划容量。
        """
        if self._sse_executor is None:
            with self._executor_lock:
                if self._sse_executor is None:
                    self._sse_executor = ThreadPoolExecutor(
                        max_workers=self._sse_max_workers,
                        thread_name_prefix="sse-wait",
                    )
        return self._sse_executor

    def close(self) -> None:
        """关闭运行时持有的线程资源（幂等，可在应用 shutdown 时调用）。"""
        with self._executor_lock:
            planner_executor = self._planner_executor
            sse_executor = self._sse_executor
            self._planner_executor = None
            self._sse_executor = None
        for executor in (planner_executor, sse_executor):
            if executor is not None:
                executor.shutdown(wait=False, cancel_futures=True)


def get_app_runtime(request: Request) -> AppRuntime:
    """FastAPI 依赖：返回当前应用的运行时容器。

    测试经 ``app.dependency_overrides[get_app_runtime]`` 替换为桩容器，从而
    以公开 HTTP API 为测试缝驱动整个编排链。
    """
    runtime = getattr(request.app.state, "app_runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="应用运行时未初始化")
    return runtime