# 06: 评测集 5 条 + 评测脚本

**What to build:** 落地 spec 定义的 5 条黄金样例自动化测试，全部走同一条 API 缝（TestClient + 桩运行时）；提供评测脚本，控制台逐条输出 PASS/FAIL 与原因，离线可跑、不写盘。

**Blocked by:** 03 显式降级取代伪造兜底、04 中间结果类型化 + 不可信输入隔离、05 请求层校验

**Status:** ready-for-agent

- [ ] 5 条黄金样例全部自动化：happy path（上海 3 天）／缺日期字段／搜索空结果降级／schema 非法重试仍失败显式 `failed`／恶意输入隔离
- [ ] 评测脚本离线可跑（桩运行时），控制台逐条 PASS/FAIL + 失败原因
- [ ] happy path 支持真实 Key 开关（可选实测）
- [ ] 不产生写盘行为
