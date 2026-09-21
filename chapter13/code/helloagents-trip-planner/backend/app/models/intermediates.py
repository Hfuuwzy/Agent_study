"""中间结果类型化契约：三个搜索步骤输出经 Pydantic 校验后的结构化表示。

工单 04：景点 / 天气 / 酒店步骤的输出不再以裸 Agent 文本形式进入规划上下文，
而是先经本模块的 schema 校验为类型化中间结果，再由规划提示词组装器按白名单字段消费。

模型字段对齐 amap-mcp-server 的真实返回契约（librarian 核查源码 2026-09-21）：
- ``maps_text_search`` -> ``{"suggestion": ..., "pois": [{"id", "name", "address", "typecode"}]}``
- ``maps_weather`` -> ``{"city": ..., "forecasts": [{"date", "week", "dayweather", "nightweather",
  "daytemp", "nighttemp", "daywind", "nightwind", "daypower", "nightpower"}]}``
  字段名与原样保留（不带下划线），确保生产载荷校验后数据不丢失、也不静默变空。

必填字段只约束结构性无效（缺 key / 类型错误 -> 校验失败 -> 显式降级）；
可选字段允许稀疏数据，空值由白名单渲染器处理。
"""

from pydantic import BaseModel, ConfigDict


class AttractionPOI(BaseModel):
    """高德 POI（景点）中间模型：按 amap-mcp-server 实际输出建模。"""

    model_config = ConfigDict(extra="ignore")

    name: str
    address: str = ""
    id: str = ""
    typecode: str = ""


class AttractionResult(BaseModel):
    """景点搜索步骤的类型化输出。"""

    model_config = ConfigDict(extra="ignore")

    pois: list[AttractionPOI]


class HotelPOI(BaseModel):
    """高德 POI（酒店）中间模型：与景点同源（maps_text_search），独立类型表达领域语义。"""

    model_config = ConfigDict(extra="ignore")

    name: str
    address: str = ""
    id: str = ""
    typecode: str = ""


class HotelResult(BaseModel):
    """酒店搜索步骤的类型化输出。"""

    model_config = ConfigDict(extra="ignore")

    pois: list[HotelPOI]


class WeatherForecast(BaseModel):
    """单日天气预报中间模型：字段名与 amap-mcp-server 真实契约一致（无下划线）。"""

    model_config = ConfigDict(extra="ignore")

    date: str
    dayweather: str = ""
    nightweather: str = ""
    daytemp: str = ""
    nighttemp: str = ""
    daywind: str = ""
    daypower: str = ""


class WeatherResult(BaseModel):
    """天气查询步骤的类型化输出。"""

    model_config = ConfigDict(extra="ignore")

    city: str = ""
    forecasts: list[WeatherForecast]
