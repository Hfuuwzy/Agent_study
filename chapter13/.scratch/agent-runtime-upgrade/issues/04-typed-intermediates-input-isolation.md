# 04: 中间结果类型化 + 不可信输入隔离

**What to build:** 景点 / 天气 / 酒店三个搜索步骤的输出经 Pydantic schema 校验后再进入规划上下文组装，不再把裸 Agent 文本直接拼进规划提示词；用户自由文本与工具返回内容按不可信数据隔离，注入指令不进入提示词（prompt 安全边界）。

**Blocked by:** 01 依赖注入使能 + Run 受理契约

**Status:** resolved

- [x] 景点 / 天气 / 酒店步骤输出经 Pydantic schema 校验，校验失败走显式降级语义
- [x] 规划提示词基于类型化结果组装，不再拼接裸 Agent 文本
- [x] 用户自由文本与工具返回内容按不可信数据隔离，注入指令不进入提示词
- [x] 桩测试断言：注入内容在提示词组装处被拦截

## Answer

已实现（2026-09-21，评审通过）。改动全部位于 `chapter13/code/helloagents-trip-planner/backend/`，前端与工单 05/06/07 未越界：

### 实现内容

- **类型化中间契约**：新增 `app/models/intermediates.py`——`AttractionResult / WeatherResult / HotelResult`（含 POI / 预报子模型），字段对齐 amap-mcp-server 真实输出（librarian 核查源码：text_search → `{pois:[{id,name,address,typecode}]}`、weather → `{city, forecasts:[{date,week,dayweather,nightweather,daytemp,nighttemp,daywind,nightwind,daypower,nightpower}]}`）。**天气字段名与真实契约原样一致（无下划线）**，保证生产载荷校验后数据不丢失。必填字段约束结构性无效（缺 key / 类型错误），可选字段容忍稀疏数据。
- **工具原始结果捕获**：`probe.py` 新增 `ToolResultRecorder`（按工具名保留最近一次成功返回，按步 `drain()` 隔离；景点/酒店共用 text_search 亦不串扰）；`EventEmittingTool / EventEmittingAmapTool` 增加独立 `result_capture` 通道，SSE 事件仍只带 `result_preview`，完整载荷不污染事件流。`factory.py` 按 Run 装配录制器。
- **步骤输出 = 类型化中间结果**：`trip_planner_agent.py::_run_search_step` 以工具实际返回（经 `_extract_json` 剥离 `工具 'X' 执行结果:` 前缀）为步骤输出，经 Pydantic 校验；工具失败 / 结果缺失 / schema 校验失败 / 空结果均返回显式降级（warnings + 空壳计划），校验失败额外发布 `validation_error` 事件（工单 02 预留的协议事件本次投产）。不再以"Agent 总结文本是否为空"判定失败——规划上下文只消费类型化结果。
- **规划提示词基于类型化结果组装**：`_build_planner_query` 只消费白名单字段（POI 名称/地址、天气日期/天气/温度/风），逐字段 `sanitize_untrusted()`（折叠空白/控制字符抹平"另起一节"注入通道 + 限长）后再入提示词；裸 Agent 自由文本总结不再被拼接（桩测试断言其不存在于规划 query）。
- **不可信输入隔离**：新增 `app/agents/input_isolation.py`——`contains_directive()` 命中高信号指令标记（忽略以上 / ignore previous / system prompt / 泄露 / reveal / [tool_call）即视为可疑；可疑自由文本整段丢弃（警告"已隔离自由文本输入中的可疑指令内容"）、可疑 POI / 预报条目整体丢弃（警告"xx 结果已隔离疑似注入的条目"），保证注入载荷（含未知哨兵）不进入提示词；隔离产生 warnings → 终态 `degraded`（显式降级，不伪装成功）。
- **桩对齐生产契约**：`tests/stubs.py` 的 `StubAmapTool` 默认改返回与真实 MCP 一致的 JSON；新增 `TextSearchStub` 按 keywords 区分景点/酒店返回。`StubLLM` 不变。
- **提示词拆分为纯数据表**：四个 `*_AGENT_PROMPT` 移到 `app/agents/prompts.py`（脚本逐字节核验，仅移动未改写，不触碰 spec"提示词重写"红线），`trip_planner_agent.py` 纯 LOC 495→357。

### 评审记录（双轴，Standards / Spec）

- **Standards 1 个硬性违规已修复**：天气中间模型字段名与真实 amap 契约不符（`day_weather/day_temp/...` vs 真实 `dayweather/daytemp/...`），`extra="ignore"` 下真载荷校验通过但天气字段静默置空、仍报 success——正是本工单要消灭的"无标注成功"。修复：模型/桩/渲染器统一改用真实字段名，并新增断言 `24°C~18°C` 必须流入规划上下文（防静默丢失回归）。
- **Standards 2 个硬性违规已修复**：`_run_search_step` 在"先失败、重试后成功"场景会丢弃失败证据。修复：证据随 `warnings` 透传、plan_trip 改为按"typed 是否为 None"判定硬降级（证据/隔离类警告累积到终态，不吞失败、不扔已恢复数据），新增回归用例 `test_transient_tool_failure_after_retry_keeps_evidence_and_real_plan`（degraded + 真实 days + 证据在 warnings）。
- **Spec 补强**：`preferences` 也按不可信文本做指令隔离（`_render_preferences`，与自由文本同规则），补上"用户自由文本等"的覆盖缺口；`FIELD_LIMIT` 收敛到 `input_isolation.py` 单一来源，消除跨模块重复常量。
- 基线气味（评审判定为 judgement calls，未改）：`_render_weather` 7 元组解包替代索引；`_parse_attractions/_parse_hotels` 一行包装保留（领域命名价值）；`_run_search_step` 7 参已文档化；`assert ... is not None` 仅用于窄化。

### 验证证据

- 后端：`python -m unittest discover -s tests -v` → **46/46 OK**（本工单 `test_typed_intermediates.py` 7 例：类型化结果驱动规划上下文且无裸 Agent 文本、schema 非法 → degraded + `validation_error` 事件 + 不触发规划、自由文本注入隔离、工具字段注入隔离（干净条目照常入上下文）、空 POI 列表 → degraded、MCP 前缀包裹 JSON 可解析、瞬时工具失败重试后证据保留且不丢真实计划；`test_explicit_degradation.py` 重锚定 2 例：空工具结果 → degraded、Agent 总结为空但工具结果有效 → success，明确记录工单 04 的语义迁移）。全程离线桩驱动、零新增依赖、零写盘。另含并行工单 05 的 9 例请求层校验（同工作区共存，无回归）。
- 语义迁移说明：工单 03 的"Agent 返回空结果即降级"被"类型化中间结果无效才降级"取代——规划上下文的数据源从 Agent 文本变为工具实际返回，空总结不再是失败信号（有测试固化该语义）。
- 既有 LSP：`trip_planner_agent.py / prompts.py / probe.py / factory.py / intermediates.py / input_isolation.py / stubs.py / 两个测试文件` 零诊断；`schemas.py` 的 `Field(...)` 位置参数报错为既有问题（工单 05 范围，未触碰）。
- 未跟踪文件说明：`backend/tests/test_request_validation.py` 是工单 05 并行产物（非本工单文件，未暂存、未提交）。
