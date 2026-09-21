"""事件探针：把工具调用包装为 tool_call / tool_result 事件，不触碰 Agent 内核。

设计（与 ADR-0002 一致）：SimpleAgent / MCPTool / 提示词一律不改写；探针只插在
"Agent 工具注册表 ↔ 实际工具"之间——SimpleAgent 解析出 [TOOL_CALL:...] 后调用
``tool.run(params)``，探针在调用前后各发一条事件，把"真实工具正在被调用"推给 SSE 订阅者。

- ``EventEmittingTool``      包装单个展开工具（MCPWrappedTool / StubTool 等）。
- ``EventEmittingAmapTool``  包装高德 MCP 容器（auto_expand 契约透传），展开时逐个包探针；
                             其余协议（AmapService 的 run({action,...})）原样透传给内层。
"""

from typing import Any, Callable, Dict, List

from hello_agents.tools import Tool

# 事件发布函数签名：sink(event_type: str, data: dict) -> None
EventSink = Callable[[str, dict], None]


class ToolFailureRecorder:
    """记录工具执行失败的证据（tool_result 事件携带 error 字段）。

    与 :class:`EventEmittingTool` 同源：探针发布 tool_result 事件时若带 error，
    即为"该工具实际抛错"的结构化证据（非自然语言猜测）。录制器把供探针使用的
    sink 包装为"先记录、再转发"，编排层在每步之后 drain() 取回该步的失败证据，
    用于判定步骤是否降级。录制器在 factory 里按 Run 创建，随 Run 生命周期隔离。
    """

    def __init__(self) -> None:
        self._evidence: List[str] = []

    def wrap(self, event_sink: EventSink) -> EventSink:
        """返回一个"先记录工具失败证据、再转发"的 sink。"""

        def sink(event_type: str, data: dict) -> None:
            if event_type == "tool_result" and data.get("error"):
                tool_name = data.get("tool_name", "unknown")
                self._evidence.append(f"工具 {tool_name} 执行失败: {data['error']}")
            event_sink(event_type, data)

        return sink

    def drain(self) -> List[str]:
        """取出并清空已记录的失败证据（编排层按步调用）。"""
        evidence = self._evidence
        self._evidence = []
        return evidence


class EventEmittingTool(Tool):
    """包装单个工具的探针：run 前后分别发 tool_call 与 tool_result 事件。"""

    def __init__(self, inner: Tool, emit: EventSink) -> None:
        super().__init__(name=inner.name, description=inner.description)
        self._inner = inner
        self._emit = emit

    def run(self, parameters: Dict[str, Any]) -> str:
        self._emit("tool_call", {"tool_name": self.name, "parameters": dict(parameters or {})})
        try:
            result = self._inner.run(parameters)
        except Exception as e:  # 工具执行失败：事件如实携带错误，异常继续上抛由编排层处理
            self._emit("tool_result", {"tool_name": self.name, "error": str(e)})
            raise
        self._emit("tool_result", {"tool_name": self.name, "result_preview": str(result)[:200]})
        return result

    def get_parameters(self):
        return self._inner.get_parameters()


class EventEmittingAmapTool(Tool):
    """高德 MCP 容器探针：保持 auto_expand 契约，展开出的每个工具都包一层事件探针。

    其余行为透传内层工具（如 AmapService 直接调用的 run 协议），不改变任何既有语义。
    """

    def __init__(self, inner: Tool, emit: EventSink) -> None:
        super().__init__(name=inner.name, description=inner.description)
        self._inner = inner
        self._emit = emit
        self.auto_expand = True

    def get_expanded_tools(self) -> List[Tool]:
        expander = getattr(self._inner, "get_expanded_tools", None)
        if expander is None:
            raise TypeError(f"工具 {self._inner.name} 不支持 auto_expand 展开")
        return [EventEmittingTool(t, self._emit) for t in expander()]

    def get_parameters(self):
        return self._inner.get_parameters()

    def run(self, parameters: Dict[str, Any]) -> str:
        # AmapService 等非 Run 场景直接调用时不需要事件，原样透传
        return self._inner.run(parameters)
