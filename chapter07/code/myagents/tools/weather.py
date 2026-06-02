"""天气工具 - 对齐当前安装版 hello-agents Tool API。"""

from importlib import import_module
from typing import Any

_tool_base = import_module("hello_agents.tools.base")
Tool = _tool_base.Tool
ToolParameter = _tool_base.ToolParameter


class WeatherTool(Tool):
    """返回预设城市的模拟天气数据。"""

    def __init__(self):
        super().__init__(
            name="weather",
            description="查询指定城市的天气信息",
        )
        self.weather_db = {
            "北京": {"weather": "晴天", "temp": 25, "humidity": 60},
            "上海": {"weather": "多云", "temp": 28, "humidity": 70},
            "广州": {"weather": "小雨", "temp": 30, "humidity": 85},
            "深圳": {"weather": "阴天", "temp": 29, "humidity": 80},
            "杭州": {"weather": "晴天", "temp": 26, "humidity": 65},
        }

    def run(self, parameters: dict[str, Any]) -> str:
        """查询天气并返回字符串结果。"""
        city = str(parameters.get("city") or parameters.get("input") or "").strip()
        if not city:
            return "错误：参数 'city' 不能为空。"

        data = self.weather_db.get(city)
        if not data:
            return f"{city}: 暂无天气数据。"

        return f"{city}: {data['weather']}, {data['temp']}°C, 湿度 {data['humidity']}%"

    def get_parameters(self) -> list[ToolParameter]:
        """定义工具参数。"""
        return [
            ToolParameter(
                name="city",
                type="string",
                description="城市名称，如 '北京'",
                required=True,
            )
        ]
