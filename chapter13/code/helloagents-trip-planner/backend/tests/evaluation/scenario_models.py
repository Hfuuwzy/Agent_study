"""评测场景 JSON 的信任边界解析：把 checked-in 黄金场景文件解析为类型化值。

场景 JSON 是黄金评测集的唯一事实来源（spec "Testing Decisions"：场景 JSON →
进程内请求 → 控制台 PASS/FAIL，不写盘）。本模块只在文件信任边界把 JSON 解析为
Pydantic 值；运行与断言分别在 ``evaluation.stubs / harness / checks``，测试与未来
的评测 CLI 复用同一份解析逻辑。

约定：
- ``request`` 是原样发往 ``POST /api/trip/plan`` 的载荷（不做请求级预校验），
  使"缺日期字段"这类请求层拒绝场景也能以字面载荷表示；
- ``expect.kind`` 判别式联合选择对应的断言函数（见 ``checks.assert_scenario``）；
- 定稿为 ``frozen=True``：场景值只读，与"checked-in read-only"语义一致。
"""

from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: 文本搜索（text_search）步骤桩的返回配置：默认夹具 / 空结果 / 注入可疑条目。
PoiSearchMode = Literal["default", "empty", "injected"]
#: 天气步骤桩的返回配置：默认夹具 / 空预报。
WeatherMode = Literal["default", "empty"]
#: 规划步骤的响应配置：默认合法计划 / 缺必填字段导致 schema 校验失败的非法 JSON。
PlanResponseToken = Literal["default", "schema_invalid"]
#: Unsplash 桩模式：命中 / 未命中占位 / 服务异常。
UnsplashMode = Literal["hit", "miss", "error"]


class ScenarioStubs(BaseModel):
    """场景桩配置：驱动 LLM / 高德 MCP / Unsplash 桩的构造（见 ``evaluation.stubs``）。"""

    model_config = ConfigDict(frozen=True)

    attraction_mode: PoiSearchMode = "default"
    weather_mode: WeatherMode = "default"
    hotel_mode: PoiSearchMode = "default"
    plan_response: PlanResponseToken = "default"
    unsplash_mode: UnsplashMode = "hit"
    user_sentinel: str | None = Field(
        default=None, description="用户自由文本中的注入哨兵（恶意输入场景断言用）"
    )
    tool_sentinel: str | None = Field(
        default=None, description="工具返回字段中的注入哨兵（恶意输入场景断言用）"
    )

    @model_validator(mode="after")
    def _check_sentinels_distinct(self) -> "ScenarioStubs":
        if self.user_sentinel is not None and self.user_sentinel == self.tool_sentinel:
            raise ValueError("user_sentinel 与 tool_sentinel 必须不同（互为独立哨兵）")
        return self


class ExpectRejected(BaseModel):
    """请求层拒绝场景（样例 2）：422 + 精确缺失定位/类型 + 零 Run + 零调用。"""

    model_config = ConfigDict(frozen=True)

    kind: Literal["rejected"]
    http_status: int = Field(default=422, ge=400, le=599)
    loc: list[Union[str, int]] = Field(..., description="期望的错误字段定位（如 ['body', 'end_date']）")
    error_types: list[str] = Field(..., description="期望的 Pydantic 错误类型（如 ['missing']）")


class ExpectAccepted(BaseModel):
    """受理场景（样例 1/3/4/5）：202 受理 + 终态 + 可选的结构化断言开关。"""

    model_config = ConfigDict(frozen=True)

    kind: Literal["success_structure", "degraded_empty_shell", "retry_exhausted_failed", "degraded_isolation"]
    http_status: int = Field(default=202, ge=200, le=299)
    terminal_status: Literal["success", "degraded", "failed"]
    assert_photo_miss_contract: bool = Field(
        default=False, description="额外断言图片未命中占位契约（经注入的 Unsplash 桩）"
    )
    planner_attempts: int | None = Field(
        default=None, ge=1, description="期望的规划 Agent 调用次数（如重试耗尽 = 3）"
    )
    searches_once: bool = Field(
        default=False, description="期望三个搜索步骤各执行一次（规划重试不得重跑搜索）"
    )


Expectation = Annotated[Union[ExpectRejected, ExpectAccepted], Field(discriminator="kind")]


class Scenario(BaseModel):
    """一个黄金评测场景：请求载荷 + 桩配置 + 预期。只读（frozen）。"""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="场景标识（文件名/断言路由用）")
    name: str = Field(..., description="场景名称")
    request: dict[str, object] = Field(..., description="发往 POST /api/trip/plan 的原样载荷")
    stubs: ScenarioStubs = Field(..., description="桩配置")
    expect: Expectation = Field(..., description="预期（判别式联合）")


#: 场景文件目录：与模块同在仓库中，供测试与 CLI 共享。
SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


def load_scenarios(directory: Path = SCENARIOS_DIR) -> list[Scenario]:
    """读取目录下全部 ``*.json`` 黄金场景（按文件名排序，保证顺序稳定）。"""
    scenarios: list[Scenario] = []
    for path in sorted(directory.glob("*.json")):
        scenarios.append(Scenario.model_validate_json(path.read_text(encoding="utf-8")))
    return scenarios