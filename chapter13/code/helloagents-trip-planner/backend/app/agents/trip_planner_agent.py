"""多智能体旅行规划系统（按 Run 构造：LLM 与高德工具由调用方注入，无进程级单例）。"""

import json

from .. import config as _config  # noqa: F401  # 保证 load_dotenv() 先于 hello_agents 导入
from hello_agents import SimpleAgent
from ..models.schemas import PlanningOutcome, TripRequest, TripPlan

# ============ Agent提示词 ============

ATTRACTION_AGENT_PROMPT = """你是景点搜索专家。你的任务是根据城市和用户偏好搜索合适的景点。

**重要提示:**
你必须使用工具来搜索景点!不要自己编造景点信息!

**工具调用格式:**
使用maps_text_search工具时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_text_search:keywords=景点关键词,city=城市名]`

**示例:**
用户: "搜索北京的历史文化景点"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=历史文化,city=北京]

用户: "搜索上海的公园"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=公园,city=上海]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
3. 参数用逗号分隔
"""

WEATHER_AGENT_PROMPT = """你是天气查询专家。你的任务是查询指定城市的天气信息。

**重要提示:**
你必须使用工具来查询天气!不要自己编造天气信息!

**工具调用格式:**
使用maps_weather工具时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_weather:city=城市名]`

**示例:**
用户: "查询北京天气"
你的回复: [TOOL_CALL:amap_maps_weather:city=北京]

用户: "上海的天气怎么样"
你的回复: [TOOL_CALL:amap_maps_weather:city=上海]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
"""

HOTEL_AGENT_PROMPT = """你是酒店推荐专家。你的任务是根据城市和景点位置推荐合适的酒店。

**重要提示:**
你必须使用工具来搜索酒店!不要自己编造酒店信息!

**工具调用格式:**
使用maps_text_search工具搜索酒店时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_text_search:keywords=酒店,city=城市名]`

**示例:**
用户: "搜索北京的酒店"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=酒店,city=北京]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
3. 关键词使用"酒店"或"宾馆"
"""

PLANNER_AGENT_PROMPT = """你是行程规划专家。你的任务是根据景点信息和天气信息,生成详细的旅行计划。

请严格按照以下JSON格式返回旅行计划:
```json
{
  "city": "城市名称",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "days": [
    {
      "date": "YYYY-MM-DD",
      "day_index": 0,
      "description": "第1天行程概述",
      "transportation": "交通方式",
      "accommodation": "住宿类型",
      "hotel": {
        "name": "酒店名称",
        "address": "酒店地址",
        "location": {"longitude": 116.397128, "latitude": 39.916527},
        "price_range": "300-500元",
        "rating": "4.5",
        "distance": "距离景点2公里",
        "type": "经济型酒店",
        "estimated_cost": 400
      },
      "attractions": [
        {
          "name": "景点名称",
          "address": "详细地址",
          "location": {"longitude": 116.397128, "latitude": 39.916527},
          "visit_duration": 120,
          "description": "景点详细描述",
          "category": "景点类别",
          "ticket_price": 60
        }
      ],
      "meals": [
        {"type": "breakfast", "name": "早餐推荐", "description": "早餐描述", "estimated_cost": 30},
        {"type": "lunch", "name": "午餐推荐", "description": "午餐描述", "estimated_cost": 50},
        {"type": "dinner", "name": "晚餐推荐", "description": "晚餐描述", "estimated_cost": 80}
      ]
    }
  ],
  "weather_info": [
    {
      "date": "YYYY-MM-DD",
      "day_weather": "晴",
      "night_weather": "多云",
      "day_temp": 25,
      "night_temp": 15,
      "wind_direction": "南风",
      "wind_power": "1-3级"
    }
  ],
  "overall_suggestions": "总体建议",
  "budget": {
    "total_attractions": 180,
    "total_hotels": 1200,
    "total_meals": 480,
    "total_transportation": 200,
    "total": 2060
  }
}
```

**重要提示:**
1. weather_info数组必须包含每一天的天气信息
2. 温度必须是纯数字(不要带°C等单位)
3. 每天安排2-3个景点
4. 考虑景点之间的距离和游览时间
5. 每天必须包含早中晚三餐
6. 提供实用的旅行建议
7. **必须包含预算信息**:
   - 景点门票价格(ticket_price)
   - 餐饮预估费用(estimated_cost)
   - 酒店预估费用(estimated_cost)
   - 预算汇总(budget)包含各项总费用
"""


class MultiAgentTripPlanner:
    """多智能体旅行规划系统"""

    def __init__(self, llm, amap_tool, event_sink=None, failure_recorder=None):
        """初始化多智能体系统：LLM 与高德 MCP 工具由调用方注入（真实实例或测试桩）。

        Args:
            llm: LLM 实例（须支持 invoke(messages) -> str，如 HelloAgentsLLM）
            amap_tool: 高德 MCP 工具（须支持 add_tool 的 auto_expand 展开契约，如 MCPTool）
            event_sink: 可选事件发布函数 (event_type, data) -> None；四步编排各发一条
                step_started（SSE 真实进度）。不提供则保持无事件行为。
        """
        print("🔄 开始初始化多智能体旅行规划系统...")

        try:
            self.llm = llm
            self.amap_tool = amap_tool
            self.event_sink = event_sink
            self.failure_recorder = failure_recorder

            # 共享MCP工具由调用方注入(底层只有一个MCP服务器进程)
            print("  - 使用注入的共享MCP工具...")

            # 创建景点搜索Agent
            print("  - 创建景点搜索Agent...")
            self.attraction_agent = SimpleAgent(
                name="景点搜索专家",
                llm=self.llm,
                system_prompt=ATTRACTION_AGENT_PROMPT
            )
            self.attraction_agent.add_tool(self.amap_tool)

            # 创建天气查询Agent
            print("  - 创建天气查询Agent...")
            self.weather_agent = SimpleAgent(
                name="天气查询专家",
                llm=self.llm,
                system_prompt=WEATHER_AGENT_PROMPT
            )
            self.weather_agent.add_tool(self.amap_tool)

            # 创建酒店推荐Agent
            print("  - 创建酒店推荐Agent...")
            self.hotel_agent = SimpleAgent(
                name="酒店推荐专家",
                llm=self.llm,
                system_prompt=HOTEL_AGENT_PROMPT
            )
            self.hotel_agent.add_tool(self.amap_tool)

            # 创建行程规划Agent(不需要工具)
            print("  - 创建行程规划Agent...")
            self.planner_agent = SimpleAgent(
                name="行程规划专家",
                llm=self.llm,
                system_prompt=PLANNER_AGENT_PROMPT
            )

            print(f"✅ 多智能体系统初始化成功")
            print(f"   景点搜索Agent: {len(self.attraction_agent.list_tools())} 个工具")
            print(f"   天气查询Agent: {len(self.weather_agent.list_tools())} 个工具")
            print(f"   酒店推荐Agent: {len(self.hotel_agent.list_tools())} 个工具")

        except Exception as e:
            print(f"❌ 多智能体系统初始化失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def _emit(self, event_type: str, data: dict) -> None:
        """发布一条编排事件（有 event_sink 时）；sink 异常不影响规划主流程。"""
        if self.event_sink is not None:
            try:
                self.event_sink(event_type, data)
            except Exception:
                pass

    def plan_trip(self, request: TripRequest) -> PlanningOutcome:
        """按四步流水线生成计划；搜索失败显式降级，最终规划失败向 runner 抛出。"""
        print(f"\n{'='*60}")
        print("🚀 开始多智能体协作规划旅行...")
        print(f"目的地: {request.city}")
        print(f"日期: {request.start_date} 至 {request.end_date}")
        print(f"天数: {request.travel_days}天")
        print(f"偏好: {', '.join(request.preferences) if request.preferences else '无'}")
        print(f"{'='*60}\n")

        self._emit("step_started", {"step": "attractions", "label": "搜索景点", "city": request.city})
        attraction_response = self.attraction_agent.run(self._build_attraction_query(request))
        warnings = self._step_warnings("景点搜索", attraction_response)
        if warnings:
            return self._degraded_outcome(request, warnings)

        self._emit("step_started", {"step": "weather", "label": "查询天气", "city": request.city})
        weather_response = self.weather_agent.run(f"请查询{request.city}的天气信息")
        warnings = self._step_warnings("天气查询", weather_response)
        if warnings:
            return self._degraded_outcome(request, warnings)

        self._emit("step_started", {"step": "hotels", "label": "推荐酒店", "city": request.city})
        hotel_response = self.hotel_agent.run(f"请搜索{request.city}的{request.accommodation}酒店")
        warnings = self._step_warnings("酒店搜索", hotel_response)
        if warnings:
            return self._degraded_outcome(request, warnings)

        self._emit("step_started", {"step": "plan", "label": "生成行程计划", "city": request.city})
        planner_query = self._build_planner_query(request, attraction_response, weather_response, hotel_response)
        planner_response = self.planner_agent.run(planner_query)
        trip_plan = self._parse_response(planner_response, request)
        return PlanningOutcome(plan=trip_plan, warnings=[])

    def _step_warnings(self, label: str, response: str) -> list[str]:
        evidence = self.failure_recorder.drain() if self.failure_recorder is not None else []
        if not response.strip():
            evidence.append("Agent 返回空结果")
        return [f"{label}失败: {item}" for item in evidence]

    def _degraded_outcome(self, request: TripRequest, warnings: list[str]) -> PlanningOutcome:
        return PlanningOutcome(plan=self._create_empty_shell(request), warnings=warnings)

    def _create_empty_shell(self, request: TripRequest) -> TripPlan:
        return TripPlan(
            city=request.city,
            start_date=request.start_date,
            end_date=request.end_date,
            days=[],
            weather_info=[],
            overall_suggestions=f"{request.city}行程计划暂不可用：部分信息获取失败，未生成具体行程。",
            budget=None,
        )
    
    def _build_attraction_query(self, request: TripRequest) -> str:
        """构建景点搜索查询 - 直接包含工具调用"""
        keywords = []
        if request.preferences:
            # 只取第一个偏好作为关键词
            keywords = request.preferences[0]
        else:
            keywords = "景点"

        # 直接返回工具调用格式
        query = f"请使用amap_maps_text_search工具搜索{request.city}的{keywords}相关景点。\n[TOOL_CALL:amap_maps_text_search:keywords={keywords},city={request.city}]"
        return query

    def _build_planner_query(self, request: TripRequest, attractions: str, weather: str, hotels: str = "") -> str:
        """构建行程规划查询"""
        query = f"""请根据以下信息生成{request.city}的{request.travel_days}天旅行计划:

**基本信息:**
- 城市: {request.city}
- 日期: {request.start_date} 至 {request.end_date}
- 天数: {request.travel_days}天
- 交通方式: {request.transportation}
- 住宿: {request.accommodation}
- 偏好: {', '.join(request.preferences) if request.preferences else '无'}

**景点信息:**
{attractions}

**天气信息:**
{weather}

**酒店信息:**
{hotels}

**要求:**
1. 每天安排2-3个景点
2. 每天必须包含早中晚三餐
3. 每天推荐一个具体的酒店(从酒店信息中选择)
3. 考虑景点之间的距离和交通方式
4. 返回完整的JSON格式数据
5. 景点的经纬度坐标要真实准确
"""
        if request.free_text_input:
            query += f"\n**额外要求:** {request.free_text_input}"

        return query
    
    def _parse_response(self, response: str, request: TripRequest) -> TripPlan:
        """从 Agent 响应中提取 JSON 并构造 TripPlan；任何失败向 runner 抛出（不伪造成功）。"""
        # 尝试从响应中提取JSON
        # 查找JSON代码块
        if "```json" in response:
            json_start = response.find("```json") + 7
            json_end = response.find("```", json_start)
            json_str = response[json_start:json_end].strip()
        elif "```" in response:
            json_start = response.find("```") + 3
            json_end = response.find("```", json_start)
            json_str = response[json_start:json_end].strip()
        elif "{" in response and "}" in response:
            # 直接查找JSON对象
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            json_str = response[json_start:json_end]
        else:
            raise ValueError("响应中未找到JSON数据")

        # 解析JSON
        data = json.loads(json_str)

        # 转换为TripPlan对象
        return TripPlan(**data)

