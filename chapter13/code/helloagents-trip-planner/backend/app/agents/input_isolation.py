"""不可信输入隔离：规划提示词组装前的安全边界（工单 04）。

用户自由文本（``free_text_input``）与工具返回内容都来自不可信来源，直接拼接进
规划提示词存在指令注入风险（诱导覆盖系统提示词 / 泄露 system prompt / 注入工具
调用语法）。本模块提供轻量隔离手段，不引入重型 guardrail 依赖：

- ``contains_directive``：命中高信号指令标记（覆盖 / 泄露 / 工具调用语法）即视为可疑；
- ``sanitize_untrusted``：折叠空白与控制字符（抹平"另起一节"的注入通道）并限长；
- 可疑内容按"整体隔离"处理：自由文本整段丢弃、单个 POI / 预报条目整体丢弃，
  保证注入载荷（含未知标记）不进入规划提示词。
"""

from typing import Final

#: 高信号指令注入标记（统一小写匹配）。命中任一项即整段 / 整条目隔离。
DIRECTIVE_MARKERS: Final[tuple[str, ...]] = (
    "忽略以上",
    "ignore previous",
    "ignore all",
    "system prompt",
    "泄露",
    "reveal",
    "[tool_call",
)

#: 自由文本与单字段的长度上限（超出截断）：隔离层的单一来源。
FREE_TEXT_LIMIT: Final[int] = 200
FIELD_LIMIT: Final[int] = 120
#: 天气字段渲染长度上限。
WEATHER_FIELD_LIMIT: Final[int] = 60


def contains_directive(text: str) -> bool:
    """判断不可信文本是否包含指令注入标记。"""
    lowered = text.lower()
    return any(marker in lowered for marker in DIRECTIVE_MARKERS)


def sanitize_untrusted(text: str, *, limit: int = FIELD_LIMIT) -> str:
    """折叠空白 / 控制字符为单空格并限长，抹平注入常用的"另起一节"通道。"""
    collapsed = " ".join(text.split())
    return collapsed[:limit]