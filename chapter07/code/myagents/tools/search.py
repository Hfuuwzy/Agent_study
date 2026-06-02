"""搜索工具 - 对齐当前安装版 hello-agents Tool API。"""

from importlib import import_module
from typing import Any

_tool_base = import_module("hello_agents.tools.base")
Tool = _tool_base.Tool
ToolParameter = _tool_base.ToolParameter


class SearchTool(Tool):
    """模拟搜索工具，返回预设知识库中的信息。"""

    def __init__(self):
        super().__init__(
            name="search",
            description="搜索信息获取相关知识",
        )
        self.knowledge_base = {
            "python": "Python是一种高级编程语言，以简洁易读著称。",
            "人工智能": "人工智能是计算机科学的一个分支，致力于创建智能机器。",
            "机器学习": "机器学习是AI的子集，让计算机从数据中学习模式。",
            "深度学习": "深度学习使用神经网络模拟人脑，是机器学习的重要分支。",
            "agent": "Agent 是能够感知环境、进行推理并采取行动的智能体。",
        }

    def run(self, parameters: dict[str, Any]) -> str:
        """执行搜索并返回字符串结果。"""
        query = str(parameters.get("query") or parameters.get("input") or "").lower().strip()
        if not query:
            return "错误：参数 'query' 不能为空。"

        for key, value in self.knowledge_base.items():
            if key in query or query in key:
                return f"搜索 '{query}': {value}"

        return f"未找到 '{query}' 的相关信息。"

    def get_parameters(self) -> list[ToolParameter]:
        """定义工具参数。"""
        return [
            ToolParameter(
                name="query",
                type="string",
                description="搜索关键词",
                required=True,
            )
        ]
