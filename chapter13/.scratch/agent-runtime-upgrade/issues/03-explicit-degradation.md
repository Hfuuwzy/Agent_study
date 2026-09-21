# 03: 显式降级取代伪造兜底

**What to build:** 让失败与降级成为诚实的显式状态：终态三态（`success | degraded | failed`），降级/失败时携带 `warnings` 失败清单；移除为任意城市生成北京基准假坐标的伪造兜底；图片兜底改为中性占位图或标注"示意图"，不再使用与目的地不符的城市照片；前端按三态如实渲染。

**Blocked by:** 02 后台执行 + SSE 真实进度

**Status:** resolved

- [x] 终态支持 `success / degraded / failed`，后两者必须携带 `warnings` 失败清单
- [x] 伪造坐标兜底移除：降级响应不包含虚构地点数据
- [x] 图片兜底改中性占位图或"示意图"标注，错误城市照片下线
- [x] 前端按三态渲染，降级/失败如实呈现而非伪装成功
- [x] 注入失败桩的用例：终态 `degraded` + `warnings`，页面可见

## Answer

### 实现内容

- **终态三态 + warnings 契约**：`PlanningOutcome(plan, warnings)` 作为编排层返回（`schemas.py`）；`runner.py` 按 `warnings` 空/非空映射 `success | degraded`，依赖构造或执行异常映射 `failed` 并带 `warnings`；`RunRecord / RunStatusResponse` 增加 `warnings`（独立 list 默认值），`transition()` 在锁内按 Run 防御性拷贝，杜绝跨 Run 污染；`GET /runs/{id}` 同步返回 warnings；`run_completed` SSE 事件经 `_publish_terminal()` 一律取自已提交的终态记录，保证并发查询与事件严格一致。
- **伪造兜底移除**：删除 `_create_fallback_plan`（含北京基准假坐标与占位景点）；任一搜索步骤失败（工具报错 / Agent 返回空结果）→ 返回**空壳计划** `days=[] / weather_info=[] / budget=null`，仅保留请求中的 city/日期，且不再进入后续规划提示词；最终 JSON 解析失败直接向 runner 抛出 → 显式 `failed`（不伪造成功）。
- **失败证据采集**：`probe.py::ToolFailureRecorder` 包装事件 sink——`tool_result` 事件携带 `error` 即为工具实际抛错的结构化证据（非自然语言猜测）；工厂按 Run 创建录制器，编排层每步 `drain()` 取回并隔离。
- **图片中性兜底**：`GET /api/poi/photo` 返回顶层 `photo_url / is_placeholder / warnings` 契约；未命中/服务异常均 HTTP 200 + `is_placeholder=true` + warnings；删除"仅景点名二次搜索"的错城市照片兜底；前端统一为中性 SVG 占位图（"暂无真实图片 / 示意图"），图片加载失败走同一占位路径（data:URL 不再触发 error，防递归）。
- **前端三态如实渲染**：`Home.vue` 校验终态载荷（success/degraded 无 result、degraded/failed 无 warnings 视为非法不跳转），完整终态信封 `TripRunResult{run_id,status,warnings,result,error}` 落 sessionStorage；`Result.vue` 按 success/degraded/failed 三态渲染警告卡，空壳降级不展示行程/地图/编辑/导出，`failed` 展示错误+重试；仅存在真实景点坐标时才初始化地图（以首个真实坐标居中，弃用北京默认中心）；编辑保存只更新 result、保留终态元数据；降级提示位于 `main-content` 内使导出保留。

### 验证证据

- 后端：`python -m unittest discover -s tests -v` → **29/29 OK**（新增 `test_explicit_degradation.py` 6 例：搜索失败→degraded 空壳且不进入规划提示词、空搜索结果→degraded、最终解析失败→failed 无 result、success 空 warnings 且 SSE/HTTP 一致、图片命中/未命中/异常显式、跨 Run warnings 隔离；新增 `test_photo_contract.py` 3 例：命中/未命中/服务异常 → HTTP 200 + 占位语义）。
- 前端：`npm run build`（vue-tsc + vite build）通过；LSP 无错误。
- 浏览器全链路（Playwright，注入失败桩 + 真实表单）：POST `/api/trip/plan` → 202 + run_id → SSE `run_completed`（status=degraded, warnings=["景点搜索失败: Agent 返回空结果"]）→ `/result` 可见降级告警（含 warning 全文与运行编号），`days=[] / budget=null`、DOM 无地图/编辑/导出控件、控制台 0 错误；390px 与桌面双断点截图复核无阻断缺陷（品牌标题完整、`#666` 满足对比度、`真实/不可用/不展示` 语义单元不拆分）。
- 双轴代码审查（Standards / Spec）在会话内执行：Standards 无硬性违规（类型安全、测试配对、无新依赖/落盘）；Spec 5 条验收全部满足，04/05/06/07 范围未越界。
- **说明**：`PLANNER_AGENT_PROMPT` 中的北京坐标（`116.397128/39.916527`）是给 LLM 的 JSON 格式 schema 示例，非运行时伪造兜底；降级空壳响应不包含任何坐标，满足验收标准。
