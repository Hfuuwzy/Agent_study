# 05: 请求层校验

**What to build:** 在 API 层拦截非法请求：日期格式与合法性、`start_date / end_date / travel_days` 交叉一致性；非法请求 422 拒绝并携带明确错误信息，不触发一次无谓的 Agent 运行。

**Blocked by:** 01 依赖注入使能 + Run 受理契约

**Status:** ready-for-agent

- [ ] 日期格式与合法性校验
- [ ] `start_date / end_date / travel_days` 交叉一致性校验
- [ ] 非法请求 422 拒绝并带明确错误信息，不触发 Agent 运行
- [ ] 通过 API 缝测试覆盖（对应评测集样例 2）
