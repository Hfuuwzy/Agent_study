# 02: 后台执行 + SSE 真实进度

**What to build:** Run 在后台线程执行，请求受理与执行分离；通过 SSE 事件流把运行的真实步骤（`run_started / step_started / tool_call / tool_result / run_completed`）推给前端；前端删除计时器模拟的假进度条，改为按真实事件渲染；50 分钟 Axios 长等待取消。

**Blocked by:** 01 依赖注入使能 + Run 受理契约

**Status:** resolved

- [x] Run 后台执行，请求受理立即返回，互不阻塞
- [x] SSE 事件流推送全部定义事件类型，终态事件携带 `status`
- [x] 前端假进度条下线，按真实事件流渲染当前步骤
- [x] 50 分钟 Axios 长等待取消，连接超时收缩到秒级
- [x] 浏览器实测：步骤随真实运行推进，完成态正确

## Answer

### 实现内容

- **后台执行**：`RunRunner.run()` 把"构造编排器 + 执行规划"整体放进专用规划线程池（`runner.py::_build_planner_and_plan` + `AppRuntime.planner_executor()`），请求受理（`POST /api/trip/plan` → 202 + run_id）与执行彻底分离；`RunRegistry` 进程内登记 Run 与事件通道（ADR-0003，零落盘）。
- **线程模型（评审修复）**：`AppRuntime` 提供两个独立的有界线程池——`planner_executor()`（构造+执行规划）与 `sse_executor()`（SSE 空闲等待心跳），惰性创建、共享 Lock 保证线程安全、`close()` 幂等回收（`main.py` shutdown 调用）；规划与 SSE 互不抢占，空闲订阅者不会拖慢后续 Run 的受理与执行。
- **SSE 事件流**：`GET /api/trip/runs/{run_id}/events` 以 `StreamingResponse` 推送 `run_started / step_started / tool_call / tool_result / validation_error / run_completed` 六类协议事件（`events.py::RunEventType`），迟到订阅者先收全量历史重放再进实时流；空闲时按 `SSE_HEARTBEAT_SECONDS` 心跳保活（`events.py::wait_next` 按总超时预算返回，修复了旧循环逐次重置超时导致心跳永远发不出的缺陷）；终态事件携带 `status/warnings/error/result`。
- **事件探针**：`probe.py` 在 Agent 工具注册表与实际工具之间包装展开工具，调前发 `tool_call`、调后发 `tool_result`（失败时带 `error` 字段），不改写 `SimpleAgent` 内核。
- **前端事件驱动**：`Home.vue` 删除计时器假进度，改按 SSE 事件渲染四步 `a-steps` 与工具活动状态；重放/重连事件按不可变信封身份（run_id+timestamp+type）去重，步骤推进严格单调（不回退、不误标完成）；旧订阅的迟到回调被 `activeRunId` 守卫隔离；`tool_result` 带 `error` 时如实显示失败；终态按 success/degraded/failed 三态处理，成功后经 sessionStorage 交给结果页。
- **完成态持久化健壮性（评审修复）**：`handleRunCompleted` 对 `JSON.stringify`/`sessionStorage.setItem` 做 try/catch；成功/降级终态缺少 `result` 时同样按失败处理；任意持久化失败都重置 loading、设置 runError、展示错误并阻止跳转（不携带陈旧计划进入结果页）。
- **测试确定性（评审修复）**：`RunContractTest` 改用 lifecycle TestClient（`__enter__/__exit__`）并 `runtime.close()`，消除后台 Run 任务被每次请求新建的 portal/loop 回收导致的偶发 10s 挂起；`test_executor_isolation.py` 以 `planner_max_workers=2` 收敛规划线程池而非改写事件循环默认执行器（后者的进程级副作用会污染后续测试）。
- **长等待取消**：Axios timeout 从 50 分钟（README 历史记录）收缩为 `30000` ms；前端仅保留秒级 POST 受理等待。

### 验证证据

- 后端：`python -m unittest discover -s tests -v` → **20/20 OK**（连续两轮复跑稳定性确认；含事件顺序、终态 status、失败路径、历史重放、404、慢构造不冻结事件循环、空闲窗口心跳保活、开放 SSE 不延迟第二个 Run 的 executor 隔离回归；测试缝 = 公开 HTTP API，全程桩驱动离线）。
- 前端：`npm run build`（vue-tsc + vite build）通过；`lsp_diagnostics` 无错误。
- 真机浏览器（Playwright Chromium，桩后端 + Vite）：
  - 提交后 POST 202 立即返回，页面展示真实步骤推进（搜索景点 → 查询天气 → 推荐酒店 → 生成行程计划），步骤状态 finish/process 单调推进；
  - 工具结果如实显示（✅ 成功 / ⚠️ 失败信息）；
  - `run_completed` 后 EventSource 关闭并跳转 `/result`，预算 ¥1850 与三日行程正常渲染（真实数据流经 `run_completed.result`）；
  - 控制台与应用日志无错误。

### 评审记录

- 五路评审（goal/QA/code-quality/security/context）：代码质量评审提出 2 个 MAJOR（sessionStorage 失败卡死 UI、SSE 与规划争用同一执行器）与若干 MINOR；安全评审无已确认高危（其自身 team-mode 未启用导致结论不完整）；其余通道受证书环境影响未返回有效结论。
- 上述 2 个 MAJOR 已修复并补充回归（见上）；修复后完整后端套件 20/20、前端构建通过、Chromium 全流程复测通过（含工具失败如实展示、`/result` 预算渲染、0 控制台错误）。
