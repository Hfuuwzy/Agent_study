# 01: 依赖注入使能 + Run 受理契约

**What to build:** 将进程级全局单例（LLM / 高德 MCP / 编排器）改造为按 Run 构造的运行时工厂，使外部依赖可注入测试桩；同时建立 Run 的一等契约——请求受理立即返回 `run_id`，并提供 run 状态查询端点。这是全部后续工单的使能改造，也是"测试缝 = 公开 HTTP API"成立的前提。

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] `POST /trip/plan` 立即返回受理结果与 `run_id`，不再长阻塞
- [x] 存在 run 状态查询端点，返回 `pending | running | success | degraded | failed` 之一
- [x] LLM / 高德 MCP / Unsplash 均可经运行时工厂注入测试桩，全局单例拆除
- [x] 现有端到端流程（真实 Key 运行）不回归
- [x] 通过 API 缝（TestClient + 桩运行时）测试验证上述契约——建立本仓库首个测试先例

## Answer

已实现（2026-09-14，代码评审通过）。改动全部位于 `chapter13/code/helloagents-trip-planner/backend/`：

- 新增 `app/runtime/` 包：`models.py`（RunStatus 状态机与 Run 契约模型）、`registry.py`（进程内线程安全注册表，零落盘，ADR-0003）、`runner.py`（后台执行器，`asyncio.to_thread` 承载同步 Agent 内核）、`factory.py`（`RuntimeFactory` 依赖注入工厂 + `AppRuntime` 容器 + `get_app_runtime` FastAPI 依赖）。
- 拆除全局单例：`get_llm` / `get_amap_mcp_tool` / `get_amap_service` / `get_unsplash_service` / `get_trip_planner_agent` 全部移除，替换为注入式构造（`create_llm` / `create_amap_mcp_tool` / `create_unsplash` / `AmapService(mcp_tool)` / `MultiAgentTripPlanner(llm, amap_tool)`）。
- 路由契约：`POST /api/trip/plan` 返回 202 + `{run_id, status, message}`（受理即回，后台执行）；新增 `GET /api/trip/runs/{run_id}` 状态查询（404 未知 run）；`/api/poi`、`/api/map` 改经工厂注入服务；启动不再因缺 Key 阻断（依赖惰性构造时校验）。
- 首个测试先例：`backend/tests/`（stdlib `unittest` + FastAPI TestClient，零新增依赖、零写盘、全程无网络）。`python -m unittest discover -s tests -v` → 10/10 通过：受理契约、状态枚举、success 终态（真实 TOOL_CALL 循环 + 桩工具）、failed 终态、404、桩注入实证、Unsplash/地图路由桩化、OpenAPI 枚举。

**跨工单留白（评审确认，归属后续工单）：** run 终态目前实际只产出 success/failed，`degraded` 的触发路径由工单 03（显式降级）补上；前端 `generateTripPlan` 仍消费旧的同步契约，改装 SSE/轮询由工单 02 负责。
