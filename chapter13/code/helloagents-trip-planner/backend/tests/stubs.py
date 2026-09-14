"""测试桩：经 RuntimeFactory 注入的 LLM / 高德 MCP / Unsplash 桩实现（全程无网络）。"""

import json
import re
from datetime import datetime, timedelta

import app.config  # noqa: F401  # 保证 load_dotenv() 先于 hello_agents 导入
from hello_agents.tools import Tool


class StubLLM:
    """脚本化 LLM 桩：按用户消息内容返回协议响应，模拟真实 Agent 的 TOOL_CALL 循环。

    协议要点（与 hello_agents SimpleAgent 文本协议一致）：
    - 用户消息内嵌 [TOOL_CALL:...] 时原样回显，触发工具执行
    - 收到"工具执行结果"上下文后返回最终自然语言回答
    - 天气查询返回 [TOOL_CALL:amap_maps_weather:city=...]
    - 酒店搜索返回 [TOOL_CALL:amap_maps_text_search:keywords=酒店,city=...]
    - 规划提示词返回包在 ```json 代码块内的完整 TripPlan
    """

    provider = "stub"
    model = "stub-model"

    def __init__(self, city="上海", start_date="2026-10-01", end_date="2026-10-03", travel_days=3):
        self.city = city
        self.start_date = start_date
        self.end_date = end_date
        self.travel_days = travel_days
        self.calls = 0

    def invoke(self, messages, **kwargs):
        self.calls += 1
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if "工具执行结果" in last_user:
            return "根据工具结果，已为您整理好相关信息。"
        if "请根据以下信息生成" in last_user:
            return self._plan_json()
        match = re.search(r"\[TOOL_CALL:[^\]]+\]", last_user)
        if match:
            return match.group(0)
        if "请搜索" in last_user:
            return f"[TOOL_CALL:amap_maps_text_search:keywords=酒店,city={self.city}]"
        if "天气" in last_user:
            return f"[TOOL_CALL:amap_maps_weather:city={self.city}]"
        return "好的，已了解。"

    def _plan_json(self) -> str:
        """生成对应当前请求的合法 TripPlan JSON（含 ```json 代码块，模拟 LLM 输出）。"""
        start = datetime.strptime(self.start_date, "%Y-%m-%d")
        days = []
        for i in range(self.travel_days):
            day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            days.append({
                "date": day,
                "day_index": i,
                "description": f"第{i + 1}天行程",
                "transportation": "公共交通",
                "accommodation": "经济型酒店",
                "hotel": {
                    "name": f"{self.city}快捷酒店",
                    "address": f"{self.city}市中心",
                    "location": {"longitude": 121.47, "latitude": 31.23},
                    "price_range": "300-500元",
                    "rating": "4.5",
                    "distance": "距景点2公里",
                    "type": "经济型酒店",
                    "estimated_cost": 400,
                },
                "attractions": [
                    {
                        "name": "外滩",
                        "address": f"{self.city}黄浦区中山东一路",
                        "location": {"longitude": 121.490317, "latitude": 31.240036},
                        "visit_duration": 120,
                        "description": f"{self.city}地标景点",
                        "category": "景点",
                        "ticket_price": 0,
                    },
                    {
                        "name": "豫园",
                        "address": f"{self.city}黄浦区",
                        "location": {"longitude": 121.492, "latitude": 31.227},
                        "visit_duration": 90,
                        "description": "古典园林",
                        "category": "景点",
                        "ticket_price": 40,
                    },
                ],
                "meals": [
                    {"type": "breakfast", "name": "生煎", "description": "本地早点", "estimated_cost": 30},
                    {"type": "lunch", "name": "本帮菜", "description": "午餐", "estimated_cost": 60},
                    {"type": "dinner", "name": "小笼包", "description": "晚餐", "estimated_cost": 80},
                ],
            })
        plan = {
            "city": self.city,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "days": days,
            "weather_info": [
                {
                    "date": days[i]["date"],
                    "day_weather": "多云",
                    "night_weather": "晴",
                    "day_temp": "24°C",
                    "night_temp": "18°C",
                    "wind_direction": "东南风",
                    "wind_power": "1-3级",
                }
                for i in range(self.travel_days)
            ],
            "overall_suggestions": f"{self.city}旅行建议：提前预订热门景点门票。",
            "budget": {
                "total_attractions": 80,
                "total_hotels": 1200,
                "total_meals": 510,
                "total_transportation": 60,
                "total": 1850,
            },
        }
        return "```json\n" + json.dumps(plan, ensure_ascii=False) + "\n```"


class StubTool(Tool):
    """最简单的 Tool 桩：固定返回结果，记录每次调用的参数。"""

    def __init__(self, name, description, result):
        super().__init__(name=name, description=description)
        self._result = result
        self.calls = []

    def run(self, parameters):
        self.calls.append(dict(parameters or {}))
        return self._result

    def get_parameters(self):
        return []


class StubAmapTool(Tool):
    """高德 MCP 桩容器：auto_expand 展开为独立工具，且兼容 MCPTool.run 的调用协议。"""

    def __init__(
        self,
        attractions_text="外滩\n地址: 上海黄浦区中山东一路\n坐标: 121.490317,31.240036",
        weather_text="上海 多云 24°C~18°C 东南风1-3级",
    ):
        super().__init__(name="amap", description="高德地图服务(测试桩)")
        self.auto_expand = True
        self._available_tools = [
            {"name": "maps_text_search", "description": "文本搜索POI"},
            {"name": "maps_weather", "description": "查询天气"},
        ]
        self.tools = {
            "amap_maps_text_search": StubTool("amap_maps_text_search", "文本搜索POI", attractions_text),
            "amap_maps_weather": StubTool("amap_maps_weather", "查询天气", weather_text),
        }

    def get_expanded_tools(self):
        return list(self.tools.values())

    def get_parameters(self):
        return []

    def run(self, parameters):
        """兼容 MCPTool.run 的 {action, tool_name, arguments} 协议（AmapService 直接调用）。"""
        action = parameters.get("action") or ("call_tool" if parameters.get("tool_name") else "")
        if action == "list_tools":
            return "找到 2 个工具:\n- maps_text_search: 文本搜索POI\n- maps_weather: 查询天气"
        if action == "call_tool":
            name = parameters.get("tool_name", "")
            tool = self.tools.get(f"amap_{name}") or self.tools.get(name)
            if tool is None:
                return f"错误：未找到工具 '{name}'"
            return tool.run(parameters.get("arguments", {}))
        return "错误：必须指定 action 参数或 tool_name 参数"


class StubUnsplash:
    """Unsplash 桩：固定返回一张占位图 URL，记录查询关键词。"""

    def __init__(self, photo_url="https://images.unsplash.com/stub-shanghai.jpg"):
        self.photo_url = photo_url
        self.calls = []

    def search_photos(self, query, per_page=5):
        self.calls.append(query)
        return [{
            "id": "stub-1",
            "url": self.photo_url,
            "thumb": self.photo_url,
            "description": "stub photo",
            "photographer": "stub",
        }]

    def get_photo_url(self, query):
        self.calls.append(query)
        return self.photo_url
