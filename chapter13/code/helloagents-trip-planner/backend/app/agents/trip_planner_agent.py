"""多智能体旅行规划系统（按 Run 构造：LLM 与高德工具由调用方注入，无进程级单例）。

工单 04：三个搜索步骤的输出经 Pydantic schema 校验为类型化中间结果（见
``models.intermediates``），规划提示词只基于类型化结果的白名单字段组装；用户自由
文本与工具返回内容按不可信数据隔离（见 ``input_isolation``），注入指令不进入提示词。

本模块另承载两个升级点：
- 三个搜索步骤各自**有界重试**（``search_step_retry``：3 次、指数退避 0.1s->0.2s），
  只重试失败的那一步，不重跑已成功步骤；耗尽保持显式降级（None + warnings，不伪造成功）。
- 每步 **loguru 控制台诊断**：以 ``run_id`` 为贯穿标识，记录 step / status / elapsed_ms /
  error（含重试与耗尽），不写日志文件、不改变执行行为。
"""

import json
import time
from typing import Callable, Protocol, Sequence, TypeVar, Union

from loguru import logger
from pydantic import ValidationError

from .. import config as _config  # noqa: F401  # 保证 load_dotenv() 先于 hello_agents 导入
from hello_agents import SimpleAgent
from ..models.intermediates import (
    AttractionPOI,
    AttractionResult,
    HotelPOI,
    HotelResult,
    WeatherForecast,
    WeatherResult,
)
from ..models.schemas import PlanningOutcome, TripRequest, TripPlan
from .final_plan_retry import FINAL_PLAN_MAX_ATTEMPTS, FinalPlanError, plan_final_with_retry
from .search_step_retry import SEARCH_STEP_MAX_ATTEMPTS, retry_search_step
from .input_isolation import (
    FIELD_LIMIT,
    FREE_TEXT_LIMIT,
    WEATHER_FIELD_LIMIT,
    contains_directive,
    sanitize_untrusted,
)
from .prompts import ATTRACTION_AGENT_PROMPT, HOTEL_AGENT_PROMPT, PLANNER_AGENT_PROMPT, WEATHER_AGENT_PROMPT

#: Agent 的 run 契约：接收用户输入文本，返回回答文本。
class _AgentRunner(Protocol):
    def run(self, input_text: str) -> str: ...


_POI_RESULT = TypeVar("_POI_RESULT", bound=AttractionResult | HotelResult)
_STEP_RESULT = TypeVar("_STEP_RESULT")

class MultiAgentTripPlanner:
    """多智能体旅行规划系统"""

    def __init__(
        self,
        llm,
        amap_tool,
        event_sink=None,
        failure_recorder=None,
        result_recorder=None,
        search_sleep: Callable[[float], None] = time.sleep,
    ):
        """初始化多智能体系统：LLM 与高德 MCP 工具由调用方注入（真实实例或测试桩）。

        Args:
            llm: LLM 实例（须支持 invoke(messages) -> str，如 HelloAgentsLLM）
            amap_tool: 高德 MCP 工具（须支持 add_tool 的 auto_expand 展开契约，如 MCPTool）
            event_sink: 可选事件发布函数 (event_type, data) -> None；四步编排各发一条
                step_started（SSE 真实进度）。不提供则保持无事件行为。
            failure_recorder: 可选 ToolFailureRecorder（工具失败证据，按 Run 隔离）。
            result_recorder: 可选 ToolResultRecorder（工具成功原始结果，供中间结果类型化）。
            search_sleep: 搜索步骤重试的等待函数；生产默认 time.sleep，测试可注入记录桩。
        """
        print("🔄 开始初始化多智能体旅行规划系统...")

        try:
            self.llm = llm
            self.amap_tool = amap_tool
            self.event_sink = event_sink
            self.failure_recorder = failure_recorder
            self.result_recorder = result_recorder
            self._run_id: str | None = None
            self._search_sleep = search_sleep

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

            print("✅ 多智能体系统初始化成功")
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

    def plan_trip(self, request: TripRequest, run_id: str | None = None) -> PlanningOutcome:
        """按四步流水线生成计划；搜索步骤输出经类型化中间结果校验，失败显式降级。

        Args:
            request: 旅行请求。
            run_id: 本次运行的唯一标识，用于 loguru 步骤诊断的贯穿关联；由 runner 注入。
        """
        self._run_id = run_id
        print(f"\n{'='*60}")
        print("🚀 开始多智能体协作规划旅行...")
        print(f"目的地: {request.city}")
        print(f"日期: {request.start_date} 至 {request.end_date}")
        print(f"天数: {request.travel_days}天")
        print(f"偏好: {', '.join(request.preferences) if request.preferences else '无'}")
        print(f"{'='*60}\n")

        step_warnings: list[str] = []

        attractions, warnings = self._run_search_step(
            request=request,
            step="attractions",
            label="景点搜索",
            agent=self.attraction_agent,
            query=self._build_attraction_query(request),
            tool_name="amap_maps_text_search",
            parser=self._parse_attractions,
        )
        if attractions is None:
            return self._degraded_outcome(request, warnings)
        step_warnings += warnings

        weather, warnings = self._run_search_step(
            request=request,
            step="weather",
            label="天气查询",
            agent=self.weather_agent,
            query=f"请查询{request.city}的天气信息",
            tool_name="amap_maps_weather",
            parser=self._parse_weather,
        )
        if weather is None:
            return self._degraded_outcome(request, warnings)
        step_warnings += warnings

        hotels, warnings = self._run_search_step(
            request=request,
            step="hotels",
            label="酒店搜索",
            agent=self.hotel_agent,
            query=f"请搜索{request.city}的{request.accommodation}酒店",
            tool_name="amap_maps_text_search",
            parser=self._parse_hotels,
        )
        if hotels is None:
            return self._degraded_outcome(request, warnings)
        step_warnings += warnings

        self._emit("step_started", {"step": "plan", "label": "生成行程计划", "city": request.city})
        planner_query, isolation_warnings = self._build_planner_query(
            request, attractions, weather, hotels
        )
        # 最终规划有界重试（最多 3 次总尝试）：仅当规划响应无法解析/校验为
        # TripPlan 时重试规划器本身；已完成的搜索步骤不会被再次执行。
        plan_started = time.monotonic()

        def on_plan_retry(next_attempt: int, delay: float) -> None:
            logger.warning(
                "step_retrying run_id={} step=plan label=生成行程计划 next_attempt={} max_attempts={} backoff_s={} delay_ms={}",
                self._run_id, next_attempt, FINAL_PLAN_MAX_ATTEMPTS, delay, int(delay * 1000),
            )

        try:
            trip_plan = plan_final_with_retry(
                run=lambda: self.planner_agent.run(planner_query),
                parse=lambda response: self._parse_response(response, request),
                on_retry=on_plan_retry,
            )
            elapsed_ms = int((time.monotonic() - plan_started) * 1000)
            logger.info(
                "step_completed run_id={} step=plan label=生成行程计划 status=success elapsed_ms={}",
                self._run_id, elapsed_ms,
            )
        except FinalPlanError as e:
            elapsed_ms = int((time.monotonic() - plan_started) * 1000)
            logger.error(
                "step_exhausted run_id={} step=plan label=生成行程计划 attempts={} max_attempts={} elapsed_ms={} error={}",
                self._run_id, e.attempts, FINAL_PLAN_MAX_ATTEMPTS, elapsed_ms, e.last_error,
            )
            raise
        return PlanningOutcome(plan=trip_plan, warnings=step_warnings + isolation_warnings)

    def _drain_failure_evidence(self, label: str) -> list[str]:
        """取回本步骤工具执行的失败证据（tool_result 事件携带 error 的结构化证据）。"""
        evidence = self.failure_recorder.drain() if self.failure_recorder is not None else []
        return [f"{label}失败: {item}" for item in evidence]

    def _run_search_step(
        self,
        request: TripRequest,
        step: str,
        label: str,
        agent: _AgentRunner,
        query: str,
        tool_name: str,
        parser: Callable[[str], tuple[_STEP_RESULT | None, str | None]],
    ) -> tuple[_STEP_RESULT | None, list[str]]:
        """执行一个搜索步骤并返回类型化中间结果。

        步骤输出 = 工具实际返回经 Pydantic schema 校验后的类型化结果，而非 Agent 的
        自由文本。工具失败 / 结果缺失 / schema 校验失败 / 空结果均返回 (None, warnings)
        并由调用方显式降级，不伪造成功。校验失败时额外发布 ``validation_error`` 事件。

        参数较多（7 个）是故意的：一个步骤的调用捆绑了互不相关的独立输入（步骤标识 /
        Agent / 查询 / 工具名 / 解析器），合并为值对象只会为一处调用增加一层包装。

        Returns:
            (typed, warnings)：成功返回 (typed, [])；失败返回 (None, warnings)。
        """
        self._emit("step_started", {"step": step, "label": label, "city": request.city})
        step_started = time.monotonic()

        def attempt() -> tuple[_STEP_RESULT | None, list[str], dict | None]:
            """执行一次完整搜索尝试；每次都 drain 录制器，隔离前一次结果。"""
            agent.run(query)
            warnings = self._drain_failure_evidence(label)
            raw_results = self.result_recorder.drain() if self.result_recorder is not None else {}
            raw = raw_results.get(tool_name, "")
            if not raw:
                if not warnings:
                    warnings.append(f"{label}失败: 未捕获到工具返回结果")
                return None, warnings, None
            typed, error = parser(raw)
            if error is not None:
                warnings.append(f"{label}失败: 中间结果校验失败: {error}")
                return None, warnings, {"step": step, "label": label, "error": error}
            # 即使步骤最终产出类型化结果，也要保留本步内发生过的工具失败证据
            #（如"先失败、重试后成功"），由调用方按 warnings 判定是否降级——不吞掉失败。
            return typed, warnings, None

        def on_retry(next_attempt: int, delay: float) -> None:
            logger.warning(
                "step_retrying run_id={} step={} label={} next_attempt={} max_attempts={} backoff_s={} delay_ms={}",
                self._run_id, step, label, next_attempt, SEARCH_STEP_MAX_ATTEMPTS,
                delay, int(delay * 1000),
            )

        typed, warnings, attempts, validation_error = retry_search_step(
            attempt,
            sleep=self._search_sleep,
            on_retry=on_retry,
        )
        elapsed_ms = int((time.monotonic() - step_started) * 1000)
        if typed is None:
            if validation_error is not None:
                self._emit("validation_error", validation_error)
            error = warnings[-1] if warnings else "未捕获到有效工具结果"
            logger.error(
                "step_exhausted run_id={} step={} label={} attempts={} max_attempts={} elapsed_ms={} error={}",
                self._run_id, step, label, attempts, SEARCH_STEP_MAX_ATTEMPTS, elapsed_ms, error,
            )
        else:
            status = "recovered" if attempts > 1 else "success"
            logger.info(
                "step_completed run_id={} step={} label={} status={} attempts={} max_attempts={} elapsed_ms={}",
                self._run_id, step, label, status, attempts, SEARCH_STEP_MAX_ATTEMPTS, elapsed_ms,
            )
        return typed, warnings

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

    def _build_planner_query(
        self,
        request: TripRequest,
        attractions: AttractionResult,
        weather: WeatherResult,
        hotels: HotelResult,
    ) -> tuple[str, list[str]]:
        """基于类型化中间结果组装规划提示词：只消费白名单字段并做不可信隔离。

        Returns:
            (query, warnings)：warnings 记录被隔离的可疑条目 / 自由文本（终态降级依据）。
        """
        attraction_context, isolation_warnings = self._render_pois(attractions.pois, "景点")
        hotel_context, hotel_warnings = self._render_pois(hotels.pois, "酒店")
        isolation_warnings += hotel_warnings
        weather_context, weather_warnings = self._render_weather(weather.forecasts)
        isolation_warnings += weather_warnings

        preferences, preference_warnings = self._render_preferences(request.preferences)
        isolation_warnings += preference_warnings

        query = f"""请根据以下信息生成{request.city}的{request.travel_days}天旅行计划:

**基本信息:**
- 城市: {request.city}
- 日期: {request.start_date} 至 {request.end_date}
- 天数: {request.travel_days}天
- 交通方式: {request.transportation}
- 住宿: {request.accommodation}
- 偏好: {preferences}

**景点信息:**
{attraction_context or "（无景点数据）"}

**天气信息:**
{weather_context or "（无天气数据）"}

**酒店信息:**
{hotel_context or "（无酒店数据）"}

**要求:**
1. 每天安排2-3个景点
2. 每天必须包含早中晚三餐
3. 每天推荐一个具体的酒店(从酒店信息中选择)
4. 考虑景点之间的距离和交通方式
5. 返回完整的JSON格式数据
6. 景点的经纬度坐标要真实准确
"""
        if request.free_text_input:
            if contains_directive(request.free_text_input):
                isolation_warnings.append("已隔离自由文本输入中的可疑指令内容")
            else:
                free_text = sanitize_untrusted(request.free_text_input, limit=FREE_TEXT_LIMIT)
                query += f"\n**额外要求:** {free_text}"

        return query, isolation_warnings

    def _render_preferences(self, preferences: list[str]) -> tuple[str, list[str]]:
        """渲染用户偏好为单行白名单上下文；含指令标记的偏好整体隔离（与自由文本同规则）。"""
        clean: list[str] = []
        warnings: list[str] = []
        for preference in preferences:
            if contains_directive(preference):
                warnings.append("已隔离偏好中的可疑指令内容")
                continue
            clean.append(sanitize_untrusted(preference, limit=FIELD_LIMIT))
        if not clean:
            return "无", warnings
        return ", ".join(clean), warnings

    def _render_pois(
        self, pois: Sequence[Union[AttractionPOI, HotelPOI]], kind: str
    ) -> tuple[str, list[str]]:
        """渲染 POI 白名单字段（名称 / 地址）；可疑条目整体隔离并记入 warnings。"""
        lines: list[str] = []
        warnings: list[str] = []
        for poi in pois:
            raw_name = poi.name or ""
            raw_address = poi.address or ""
            if contains_directive(raw_name) or contains_directive(raw_address):
                warnings.append(f"{kind}结果已隔离疑似注入的条目")
                continue
            rendered = sanitize_untrusted(raw_name, limit=FIELD_LIMIT)
            if raw_address:
                rendered += f"（{sanitize_untrusted(raw_address, limit=FIELD_LIMIT)}）"
            lines.append(f"- {rendered}")
        return "\n".join(lines), warnings

    def _render_weather(self, forecasts: list[WeatherForecast]) -> tuple[str, list[str]]:
        """渲染天气白名单字段；可疑预报条目整体隔离并记入 warnings。"""
        lines: list[str] = []
        warnings: list[str] = []
        for day in forecasts:
            raw = (
                day.date,
                day.dayweather,
                day.nightweather,
                day.daytemp,
                day.nighttemp,
                day.daywind,
                day.daypower,
            )
            if any(contains_directive(field) for field in raw):
                warnings.append("天气结果已隔离疑似注入的预报条目")
                continue
            date, day_weather, night_weather, day_temp, night_temp, wind_direction, wind_power = (
                sanitize_untrusted(field, limit=WEATHER_FIELD_LIMIT) for field in raw
            )
            lines.append(
                f"- {date}: {day_weather}/{night_weather} {day_temp}°C~{night_temp}°C {wind_direction}{wind_power}"
            )
        return "\n".join(lines), warnings

    def _parse_attractions(self, raw: str) -> tuple[AttractionResult | None, str | None]:
        """解析景点搜索原始返回为类型化中间结果；失败返回 (None, 原因)。"""
        return self._parse_poi_result(raw, AttractionResult)

    def _parse_hotels(self, raw: str) -> tuple[HotelResult | None, str | None]:
        """解析酒店搜索原始返回为类型化中间结果；失败返回 (None, 原因)。"""
        return self._parse_poi_result(raw, HotelResult)

    def _parse_poi_result(
        self, raw: str, model: type[_POI_RESULT]
    ) -> tuple[_POI_RESULT | None, str | None]:
        """解析 POI 类（景点 / 酒店）原始返回；结构性非法或空结果视为无效。"""
        data = _extract_json(raw)
        if data is None:
            return None, "工具返回不是可解析的 JSON"
        try:
            result = model.model_validate(data)
        except ValidationError as e:
            return None, self._validation_error_text(e)
        if not result.pois:
            return None, "返回空结果"
        return result, None

    def _parse_weather(self, raw: str) -> tuple[WeatherResult | None, str | None]:
        """解析天气搜索原始返回为类型化中间结果；结构性非法或空结果视为无效。"""
        data = _extract_json(raw)
        if data is None:
            return None, "工具返回不是可解析的 JSON"
        try:
            result = WeatherResult(**data)
        except ValidationError as e:
            return None, self._validation_error_text(e)
        if not result.forecasts:
            return None, "返回空结果"
        return result, None

    @staticmethod
    def _validation_error_text(e: ValidationError) -> str:
        """把 Pydantic 校验错误压成单行摘要（loc: msg），便于写入降级警告。"""
        errors = e.errors()
        if not errors:
            return "schema 校验失败"
        first = errors[0]
        loc = ".".join(str(part) for part in first.get("loc", ()))
        message = first.get("msg", "")
        return f"{loc}: {message}" if loc else message
    
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
        if not isinstance(data, dict):
            # 结构性非法（如 JSON 数组）统一以 ValueError 表达，纳入重试判定
            raise ValueError("响应中的 JSON 不是对象，无法构造行程计划")

        # 转换为TripPlan对象
        return TripPlan(**data)


def _extract_json(raw: str) -> dict | None:
    """从工具原始返回中提取 JSON 对象（容忍 MCP 前缀包装与非 JSON 噪音）。

    生产路径（MCPTool.run）返回 ``工具 'X' 执行结果:\\n{...}`` 前缀字符串；
    桩实现直接返回 JSON 字符串。先剥离前缀再解析，失败时回退到首尾花括号切片。
    """
    text = raw.strip()
    if "执行结果:" in text:
        text = text.split("执行结果:", 1)[1].strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None
