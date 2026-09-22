"""测试桩：经 RuntimeFactory 注入的 LLM / 高德 MCP / Unsplash 桩实现（全程无网络）。"""

import json
import re
import time
from datetime import datetime, timedelta
from typing import Optional

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

    def __init__(
        self,
        city="上海",
        start_date="2026-10-01",
        end_date="2026-10-03",
        travel_days=3,
        delay_per_invoke=0.0,
        plan_response=None,
        tool_result_response=None,
    ):
        self.city = city
        self.start_date = start_date
        self.end_date = end_date
        self.travel_days = travel_days
        self.calls = 0
        self.delay_per_invoke = delay_per_invoke
        # 可注入失败响应：plan_response 覆盖规划提示词回答，tool_result_response 覆盖工具结果后的回答
        self.plan_response = plan_response
        self.tool_result_response = tool_result_response
        # 记录每次 invoke 的最后一条用户消息，便于断言"某提示词未被调用"
        self.recorded_queries = []

    def invoke(self, messages, **kwargs):
        self.calls += 1
        if self.delay_per_invoke:
            time.sleep(self.delay_per_invoke)
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        self.recorded_queries.append(last_user)
        if "工具执行结果" in last_user:
            if self.tool_result_response is not None:
                return self.tool_result_response
            return "根据工具结果，已为您整理好相关信息。"
        if "请根据以下信息生成" in last_user:
            if self.plan_response is not None:
                return self.plan_response
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

    def __init__(self, name, description, result, error=None):
        super().__init__(name=name, description=description)
        self._result = result
        self._error = error
        self.calls = []

    def run(self, parameters):
        self.calls.append(dict(parameters or {}))
        if self._error is not None:
            raise self._error
        return self._result

    def get_parameters(self):
        return []


DEFAULT_ATTRACTIONS_JSON = json.dumps({
    "pois": [
        {"id": "B0001", "name": "外滩", "address": "上海黄浦区中山东一路", "typecode": "风景名胜"},
        {"id": "B0002", "name": "豫园", "address": "上海黄浦区", "typecode": "风景名胜"},
    ],
}, ensure_ascii=False)

DEFAULT_HOTELS_JSON = json.dumps({
    "pois": [
        {"id": "H0001", "name": "上海快捷酒店", "address": "上海静安区南京西路", "typecode": "住宿服务"},
    ],
}, ensure_ascii=False)

DEFAULT_WEATHER_JSON = json.dumps({
    "city": "上海",
    "forecasts": [
        {
            "date": "2026-10-01", "dayweather": "多云", "nightweather": "晴",
            "daytemp": "24", "nighttemp": "18", "daywind": "东南风", "daypower": "1-3级",
        },
        {
            "date": "2026-10-02", "dayweather": "晴", "nightweather": "多云",
            "daytemp": "26", "nighttemp": "19", "daywind": "东南风", "daypower": "1-3级",
        },
        {
            "date": "2026-10-03", "dayweather": "小雨", "nightweather": "阴",
            "daytemp": "22", "nighttemp": "17", "daywind": "东风", "daypower": "3-4级",
        },
    ],
}, ensure_ascii=False)


class TextSearchStub(StubTool):
    """文本搜索桩：按 keywords 区分景点 / 酒店，返回结构化 JSON（与真实契约一致）。

    景点步骤的查询关键词来自用户偏好（如"历史文化"），酒店步骤固定为"酒店/宾馆"，
    据此分流返回不同 POI 列表，模拟真实 amap-mcp-server 的行为。
    """

    def __init__(self, attractions_text=DEFAULT_ATTRACTIONS_JSON, hotel_text=DEFAULT_HOTELS_JSON):
        super().__init__("amap_maps_text_search", "文本搜索POI", "")
        self._attractions_text = attractions_text
        self._hotel_text = hotel_text

    def run(self, parameters):
        self.calls.append(dict(parameters or {}))
        keywords = str((parameters or {}).get("keywords", ""))
        if "酒店" in keywords or "宾馆" in keywords:
            return self._hotel_text
        return self._attractions_text


class StubAmapTool(Tool):
    """高德 MCP 桩容器：auto_expand 展开为独立工具，且兼容 MCPTool.run 的调用协议。

    工具返回与 amap-mcp-server 真实契约一致的结构化 JSON（librarian 核查 2026-09-21）：
    景点 / 酒店 text_search -> ``{"pois": [{"id", "name", "address", "typecode"}]}``；
    天气 -> ``{"city", "forecasts": [{"date", "day_weather", ...}]}``。
    供中间结果类型化（工单 04）按真实输出形状解析。
    """

    def __init__(
        self,
        attractions_text=DEFAULT_ATTRACTIONS_JSON,
        weather_text=DEFAULT_WEATHER_JSON,
        hotel_text=DEFAULT_HOTELS_JSON,
    ):
        super().__init__(name="amap", description="高德地图服务(测试桩)")
        self.auto_expand = True
        self._available_tools = [
            {"name": "maps_text_search", "description": "文本搜索POI"},
            {"name": "maps_weather", "description": "查询天气"},
        ]
        self.tools = {
            "amap_maps_text_search": TextSearchStub(attractions_text, hotel_text),
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

    def get_photo_url(self, query) -> Optional[str]:
        self.calls.append(query)
        return self.photo_url
