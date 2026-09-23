# 06: 评测集 5 条 + 评测脚本

**What to build:** 落地 spec 定义的 5 条黄金样例自动化测试，全部走同一条 API 缝（TestClient + 桩运行时）；提供评测脚本，控制台逐条输出 PASS/FAIL 与原因，离线可跑、不写盘。

**Blocked by:** 03 显式降级取代伪造兜底、04 中间结果类型化 + 不可信输入隔离、05 请求层校验

**Status:** resolved

- [x] 5 条黄金样例全部自动化：happy path（上海 3 天）／缺日期字段／搜索空结果降级／schema 非法重试仍失败显式 `failed`／恶意输入隔离
- [x] 评测脚本离线可跑（桩运行时），控制台逐条 PASS/FAIL + 失败原因
- [x] happy path 支持真实 Key 开关（可选实测）
- [x] 不产生写盘行为

## Answer

### 实现内容

- **5 条黄金评测集落地为 checked-in 场景 JSON**（`backend/tests/evaluation/scenarios/01..05`），请求载荷原样发往唯一公开 HTTP 测试缝（FastAPI `TestClient` + 注入桩运行时），每条场景声明 `stubs`（桩行为）与 `expect`（判别式预期）：
  - `happy_path` → 202 受理 → `success`，3 天结构完整 + 图片未命中走占位契约（`assert_photo_miss_contract`）；
  - `missing_date` → 请求层 422 拒绝，`loc` 精确定位 `['body','end_date']`，零 Run 受理、零 LLM/工具调用（健康检查 `runs_total` 保持 0）；
  - `empty_search` → `degraded` 诚实空壳（`days/weather_info=[]`、`budget=null`、保留总体建议），不触发规划、不含伪造坐标；
  - `schema_retry_exhausted` → 规划响应缺必填字段（Pydantic 校验必然失败）→ 生产有界重试 3 次仍失败 → 显式 `failed`（`result=null` + `error` + `warnings`），搜索步骤不重跑（SSE `tool_call` 计数恒为 `{text_search: 2, weather: 1}`）；
  - `malicious_input` → 用户自由文本与工具返回双哨兵注入均被隔离、不进规划提示词，干净 POI（外滩）保留并产出真实计划，终态 `degraded` 带隔离告警。
- **共享评测基础设施**（`backend/tests/evaluation/`）：`scenario_models.py`（frozen Pydantic 解析，判别式联合 + 哨兵互异校验）、`stubs.py`（按场景配置构造全新桩实例）、`harness.py`（构造新鲜桩运行时 → `POST` 受理 → 有界轮询终态 → SSE 全量重放，类型化观测结果）、`assert_support.py`（类型化 JSON 收窄 + SSE 契约 + 搜索计数共享断言）、`checks.py`（`assert_scenario` 唯一公开断言入口，按 `expect.kind` 穷尽路由，`assert_never` 兜底）。
- **最终规划有界重试**（`backend/app/agents/final_plan_retry.py`，新模块 + `trip_planner_agent.py` 接入）：只重试"规划响应无法解析/校验为 TripPlan"（`ValueError` 家族：`JSONDecodeError` / Pydantic `ValidationError` / 未找到 JSON），总尝试上限 3 次、指数退避 `0.1s → 0.2s`（`sleep` 可注入供单元测试记录延迟序列）；三个搜索步骤已完成固化，绝不重跑；耗尽抛 `FinalPlanError(attempts, last_error)`，由 runner 如实落 `failed`。
- **评测 CLI**（`backend/evaluate.py`）：默认离线跑全部 5 条，逐条 `PASS/FAIL <id>: <reason>` + `SUMMARY passed=N failed=N total=N mode=offline|real`；退出码 0=全过 / 1=存在失败或未预期错误 / 2=用法错误、未知场景或真实模式预检失败；运行期应用噪音（print/loguru）捕获进内存缓冲，stdout 保持纯净；顶层宽捕获把未预期异常压成单行净化原因（CLI 即进程边界）。
- **真实 Key 快乐路径**（`tests/evaluation/real_mode.py`）：仅 `--real --case happy_path` 显式进入；预检（LLM Key / 高德 Key / `uvx` 可用性）失败抛 `RealPreflightError` → 退出 2，**绝不静默回退桩**；通过后经 `AppRuntime.default()` + 依赖覆写走同一条 HTTP 缝，校验"上海 3 天 success 结构"但不比较桩夹具的具体坐标/名称。
- **零写盘过程级证明**（`tests/evaluation/offline_guard.py` + `guarded_worker.py`）：`sys.addaudithook` 在 import app/evaluate **之前**安装（进程全局、不可移除），拦截写文件（mode/flags 双重判定）、文件树变更、外部 socket（DNS/连接/监听，仅限定回环豁免）、子进程派生；修复了守卫前 `tempfile.gettempdir()` 首次调用会写探针文件的隐患（`set_tempdir_from_env` 只读复用 TEMP/TMP 目录）；worker 支持四类负向对照探测。

### 验证证据

- 后端全量回归：`python -B -m unittest discover -s tests` → **73/73 OK**（含既有 64 + 本工单新增）。
- 定向测试：`test_final_plan_retry`（API 缝：JSON/schema 非法一次恢复→success、始终非法 3 次→failed、搜索不重跑）4/4；`test_final_plan_retry_unit`（退避序列 `[0.1, 0.2]`、`[0.1]`、`[]`）3/3；`test_evaluate_cli`（5 PASS+SUMMARY 输出纯净、`--case` 单选、未知场景/`--real` 非法组合退出 2、带 Key 离线默认不切换、缺 Key 预检退出 2 不回退）6/6；`test_offline_guard`（受保护全量运行零违规、四类负向探测全部拦截、AST 级证明无 `gettempdir` 路径、探测目标不预先存在）9/9。
- 进程级实测：`python -B evaluate.py` → 连续两次输出**逐字节一致**（确定性），退出 0；`python -B -m tests.evaluation.guarded_worker` → 5 PASS + `GUARD violations=0`，退出 0；`--probe write/mutation/socket/subprocess` 全部 `GUARD BLOCKED`、退出 1、写/目录探测目标保持不存在；`--real --case happy_path`（Key 置空）→ `REAL_PREFLIGHT` 列出 LLM/AMAP 缺失、退出 2、无 PASS、无离线回退。
- 质量门：Ruff `check` 全绿；变更文件 LSP 诊断零错误；`git diff --check` 干净；模块均低于 250 LOC 约定上限。
- 变更范围：仅 `app/agents/final_plan_retry.py`、`app/agents/trip_planner_agent.py`、`evaluate.py`、`tests/evaluation/**`、`tests/test_final_plan_retry*.py`、`tests/test_evaluate_cli.py`、`tests/test_offline_guard.py` 与本工单文件；未触碰 03/04/05/07 范围。
