# 02: 后台执行 + SSE 真实进度

**What to build:** Run 在后台线程执行，请求受理与执行分离；通过 SSE 事件流把运行的真实步骤（`run_started / step_started / tool_call / tool_result / run_completed`）推给前端；前端删除计时器模拟的假进度条，改为按真实事件渲染；50 分钟 Axios 长等待取消。

**Blocked by:** 01 依赖注入使能 + Run 受理契约

**Status:** ready-for-agent

- [ ] Run 后台执行，请求受理立即返回，互不阻塞
- [ ] SSE 事件流推送全部定义事件类型，终态事件携带 `status`
- [ ] 前端假进度条下线，按真实事件流渲染当前步骤
- [ ] 50 分钟 Axios 长等待取消，连接超时收缩到秒级
- [ ] 浏览器实测：步骤随真实运行推进，完成态正确
