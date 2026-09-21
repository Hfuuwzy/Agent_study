# 05: 请求层校验

**What to build:** 在 API 层拦截非法请求：日期格式与合法性、`start_date / end_date / travel_days` 交叉一致性；非法请求 422 拒绝并携带明确错误信息，不触发一次无谓的 Agent 运行。

**Blocked by:** 01 依赖注入使能 + Run 受理契约

**Status:** resolved

- [x] 日期格式与合法性校验
- [x] `start_date / end_date / travel_days` 交叉一致性校验
- [x] 非法请求 422 拒绝并带明确错误信息，不触发 Agent 运行
- [x] 通过 API 缝测试覆盖（对应评测集样例 2）

## Answer

### 实现内容

- **请求层校验全部收敛在 `TripRequest`（`app/models/schemas.py`）**，FastAPI 在路由受理前完成模型校验，非法请求 422 拒绝，`registry.create` 与后台 Agent 执行根本不发生：
  - 字段级校验（`field_validator("start_date", "end_date")`）：严格 `YYYY-MM-DD` 格式（`re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")`，全角数字/非零填充/多余字符一律拒绝）+ 日历合法性（`date.fromisoformat` 拒绝 2026-02-30、2026-04-31 等不存在日期）；错误 `loc` 精确定位到字段。
  - 模型级校验（`model_validator(mode="after")`）：`end_date < start_date` 拒绝；`travel_days` 与日期区间一致性按**含首尾**口径 `(end - start).days + 1` 校验（与前端 Home.vue `end.diff(start,'day') + 1` 同一语义），不一致则说明期望天数。
- **错误信息明确**：`detail[].msg` 携带"日期格式必须为 YYYY-MM-DD / 非法日期: xxx / 结束日期不能早于开始日期 / travel_days 与日期区间不一致：日期区间为 N 天，实际传入 M 天"；缺字段保留标准 `Field required`（type=missing）；既有 `ge=1, le=30` 边界保留不变。
- **零 Run / 零 Agent 断言**：每个拒绝用例通过公开 `GET /api/trip/health` 的 `runs_total` 断言零 Run 受理，并断言 LLM 桩零调用（`calls == 0`、`recorded_queries == []`），证明校验失败不浪费一次 Agent 运行（用户故事 7）；不直接断言内部 registry 状态（遵循 spec"只测外部行为 / 唯一测试缝 = 公开 HTTP API"）。
- 前端天然一致：Home.vue 提交前按同一规则推导 `travel_days`，合法表单必然通过新校验，无前端改动。

### 验证证据

- 新增 `backend/tests/test_request_validation.py` 9 例（unittest + FastAPI TestClient + 注入桩，全程离线）：
  - 拒绝路径：缺日期字段（评测集样例 2，type=missing + loc 定位）、类型错误、格式错误矩阵（`2026/10/01`、`2026-2-01`、`20260201`、前导空格、全角数字）、非法日历矩阵（2-30/4-31/00-01/13-01/0000）、`end < start`、`travel_days` 与日期区间不符（1/2/4 vs 期望 3）、越界（0/31）；
  - 接受路径：合法请求 202 受理且桩驱动走通 success 终态；边界日期（闰日单天、月末跨月 `1-31→2-01`、跨年 `12-31→1-01`、30 天上限）均 202 受理——保证不误伤一致请求。
- 实测 422 载荷样例：`{"detail":[{"type":"value_error","loc":["body","start_date"],"msg":"Value error, 非法日期: 2026-02-30"}]}`；缺字段样例 `{"detail":[{"type":"missing","loc":["body","end_date"],"msg":"Field required"}]}`。
- 后端全量回归：`python -m unittest discover -s tests` → **38/38 OK**（原 29 + 新 9，无回归、未削弱既有断言）。
- 变更范围：仅 `backend/app/models/schemas.py`（校验器）+ `backend/tests/test_request_validation.py`（新测试）+ 本工单文件；未触碰 04/06/07 范围。
