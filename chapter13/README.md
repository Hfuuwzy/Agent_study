# 第十三章：智能旅行助手（MCP 与多智能体协作的真实世界应用）

> 对应教程：[第十三章 智能旅行助手](https://github.com/datawhalechina/hello-agents/blob/main/docs/chapter13/%E7%AC%AC%E5%8D%81%E4%B8%89%E7%AB%A0%20%E6%99%BA%E8%83%BD%E6%97%85%E8%A1%8C%E5%8A%A9%E6%89%8B.md)
> 官方代码仓：`hello-agents/code/chapter13/helloagents-trip-planner`（本项目以官方 35 个文件为基线，并加入运行验证所需的少量环境适配）

---

## 1. 本章定位

从本章开始进入教程**第四部分：综合案例进阶**。前十二章我们分别学习了范式（第四章）、框架（第七章）、记忆检索（第八章）、上下文工程（第九章）、通信协议（第十章），本章把这些能力**融会贯通成一个真正能用的全栈应用**。

第一章我们写过一个 `travel_assistant.py`——一个演示 Thought-Action-Observation 循环的玩具旅行助手。本章是它的"完全体"：

| 维度 | 第一章原型 | 第十三章完整版 |
|------|-----------|---------------|
| 形态 | 单文件脚本 | 前后端分离 Web 应用 |
| 智能体 | 单 Agent + 硬编码工具 | 4 个专职 SimpleAgent 协作 |
| 工具 | 手写函数模拟 | 高德地图 MCP 服务（16+ 工具自动发现） |
| 数据 | Python 字典 | Pydantic 模型全链路校验 |
| 交互 | 命令行打印 | Vue3 表单 + 地图可视化 + 行程编辑 + 导出 |

**核心功能**：智能行程规划、地图可视化、预算计算、行程编辑、导出 PDF/图片。

## 2. 核心概念

### 2.1 数据模型：从字典到 Pydantic（13.2 节）

Web 应用中数据要经历多次转换（前端表单 → HTTP → 后端对象 → 外部 API → …），字典表示法有三大问题：字段名不统一、类型不安全、维护性差。本章解法是**自底向上**定义 Pydantic 模型层次：

```
Location (经纬度, ge/le 范围验证)
  ├── Attraction (景点: 名称/地址/位置/游览时长/门票)
  ├── Meal (餐饮: 类型/名称/预估费用)
  └── Hotel (酒店: 价格范围/评分/距离)
        ↓ 组合
     DayPlan (单日行程: 景点列表 List[Attraction] + 餐饮 + 酒店)
        ↓ 组合
     TripPlan (顶层: days + weather_info + budget + overall_suggestions)
```

两个值得注意的设计：
- **`field_validator(mode='before')` 容错**：高德返回温度是 `"16°C"` 字符串，在模型层统一剥单位转 int，业务代码不再关心格式差异。
- **FastAPI 直接复用模型**：`response_model=TripPlan` 让框架自动完成验证、序列化、OpenAPI 文档生成；前端用 TypeScript interface 镜像同一结构，前后端数据契约一份两用。

### 2.2 为什么需要多智能体（13.3 节）

单 Agent 方案的三个痛点（教程论证）：
1. **工具调用限制**：SimpleAgent 每次 `run()` 只执行一个工具，多任务需手动传递中间结果；
2. **时间成本**：ReActAgent 多轮思考串行调 LLM，总时长不可接受；
3. **提示词复杂度**：一个提示词塞四种任务逻辑 → 难维护、易出错、难调试。

解法是模仿真实旅行社的分工——四个专职 Agent：

| Agent | 职责 | 是否调用工具 |
|-------|------|-------------|
| 景点搜索专家 | 按偏好搜 POI | ✅ `amap_maps_text_search` |
| 天气查询专家 | 查城市天气 | ✅ `amap_maps_weather` |
| 酒店推荐专家 | 按住宿类型搜酒店 | ✅ `amap_maps_text_search` |
| 行程规划专家 | 整合三方输出 → JSON 计划 | ❌ 纯 LLM 整合 |

每个提示词都极简且带 few-shot 示例，只讲清楚三件事：输入什么、调用什么工具（含 `[TOOL_CALL:...]` 格式示例）、禁止编造。

### 2.3 MCP 工具集成（13.4 节）—— 本章与第十章的交汇点

**为什么不直接 requests 调高德 API？** 因为 Agent 需要"自主决策调用"，直接函数调用剥夺了智能性；且参数说明会让提示词爆炸。MCP 把这些全部封装：

```python
self.amap_tool = MCPTool(
    name="amap",
    description="高德地图服务",
    server_command=["uvx", "amap-mcp-server"],   # 启动 MCP 服务器子进程
    env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
    auto_expand=True                              # 关键：自动发现并展开所有工具
)
```

三个关键机制：
1. **stdio 子进程通信**：MCPTool 以 `uvx amap-mcp-server` 拉起子进程，JSON-RPC over stdin/stdout；
2. **`auto_expand=True` 工具爆炸**：创建 1 个 MCPTool，自动为服务器的每个工具生成独立 Tool 对象——一个实例换来 16+ 个可调用工具（`amap_maps_text_search`、`amap_maps_weather`…）；
3. **共享单例**：三个 Agent `add_tool()` 同一个 MCPTool 实例，底层只有**一个** MCP 服务器进程，节省资源且便于控制 API 频率。

### 2.4 Unsplash 图片服务的定位（13.4.4 节）

图片搜索**没有**封装成 Tool/MCP，而是在 API 路由层直接调用——因为它不需要 Agent 智能决策，只是确定性的数据增强步骤。"是否封装为工具"的判断标准：该能力是否需要 LLM 自主决定何时/如何使用。

## 3. 技术架构与目录结构

```
┌─────────────────────────────────────────────────┐
│  前端层  Vue3 + TypeScript + Vite + Ant Design   │
│         表单输入 / 结果渲染 / 地图 / 编辑 / 导出   │
└──────────────────┬──────────────────────────────┘
                   │ HTTP (Axios, POST /api/trip/plan)
┌──────────────────▼──────────────────────────────┐
│  后端层  FastAPI                                 │
│         路由 / 数据验证 / CORS / Unsplash 增强    │
├─────────────────────────────────────────────────┤
│  智能体层  HelloAgents MultiAgentTripPlanner     │
│         4 × SimpleAgent（共享 1 × MCPTool）      │
├─────────────────────────────────────────────────┤
│  外部服务层  高德 MCP(uvx) / Unsplash / LLM API  │
└─────────────────────────────────────────────────┘
```

```
chapter13/code/helloagents-trip-planner/
├── backend/
│   ├── app/
│   │   ├── agents/trip_planner_agent.py   # ★ 核心：四智能体协作系统
│   │   ├── api/main.py                    # FastAPI 入口 + CORS + startup 校验
│   │   ├── api/routes/{trip,poi,map}.py   # 三组路由
│   │   ├── models/schemas.py              # ★ Pydantic 模型层次
│   │   ├── services/{llm,unsplash,amap}_service.py
│   │   └── config.py                      # pydantic-settings 配置
│   ├── requirements.txt                   # hello-agents[protocols]>=0.2.4
│   └── .env.example                       # LLM_* / AMAP_API_KEY / UNSPLASH_*
└── frontend/
    ├── src/types/index.ts                 # TS 类型镜像后端模型
    ├── src/services/api.ts                # Axios 封装（120s 超时）
    ├── src/views/{Home,Result}.vue        # 表单页 / 结果页(地图+编辑+导出)
    └── .env.example                       # VITE_AMAP_WEB_KEY / VITE_AMAP_WEB_JS_KEY
```

## 4. 关键代码讲解

### 4.1 五步协作流水线（`trip_planner_agent.py`）

`MultiAgentTripPlanner.plan_trip()` 顺序执行：

```
步骤1 景点搜索 → 步骤2 天气查询 → 步骤3 酒店推荐 → 步骤4 规划整合 → 步骤5 JSON 解析
```

细节亮点：
- **查询内嵌工具引导**：`_build_attraction_query()` 生成的 query 里直接附上完整的 `[TOOL_CALL:...]` 文本。这是对齐 SimpleAgent 文本协议的实用技巧——把"期望的工具调用"作为示例喂给 LLM，显著降低格式出错率。
- **三级 JSON 提取降级**（`_parse_response`）：`\`\`\`json 代码块` → 裸 \`\`\` 代码块 → 首个 `{` 到末个 `}` 的裸对象。LLM 输出格式不稳定时的工程兜底。
- **fallback 计划**：~~任何一步失败都不让请求 500，而是生成占位行程保证前端可渲染。~~（⚠️ 已被 9.x 升级取代：旧实现会生成以北京为基准的**假坐标**与占位景点并恒定 `success=True`。升级后改为**显式降级三态** `success | degraded | failed`，降级返回不含虚构坐标的空壳计划并如实标注，见 §9.4。本节保留原教程描述供对照。）

### 4.2 提示词即契约

四个 PROMPT 常量就是四个 Agent 的全部"人格"。以规划专家为例，它要求 LLM 严格按 JSON Schema 返回（温度纯数字不带 °C、每天 2-3 景点、必含三餐、必含 budget）。**Pydantic 模型 + 提示词中的 JSON 示例 + 解析降级**三者构成完整的输出可靠性链条。

### 4.3 前端的工程细节（Result.vue）

- **~~Axios timeout=3000000~~**：~~四 Agent 串行调用叠加 LLM 自动重试，实测可能超过官方默认的 120 秒；当前学习环境将前端等待上限放宽至 50 分钟。~~（⚠️ 已被 9.x 升级取代：`POST /plan` 改为受理后立即返回 `run_id`（202），前端改接 SSE 真实进度，50 分钟长等待取消；`api.ts` 超时回落到常规 30s，见 §9.3。）
- **~~模拟进度条~~**：~~`setInterval` 每 500ms 推进进度并切换状态文案。~~（⚠️ 已被 9.x 升级取代：前端改按 SSE 六类事件渲染真实步骤 `step_started → tool_call → tool_result → …`，假计时器进度条下线，见 §9.3。）
- **编辑模式的深拷贝**：`originalPlan = JSON.parse(JSON.stringify(tripPlan))`，取消编辑可回滚；移动景点用 ES6 解构交换 `[a[i],a[j]]=[a[j],a[i]]`；保存后重新 `initMap()` 同步标记；
- **导出的已知局限**：html2canvas 无法处理高德地图的嵌套 Canvas（跨域+渲染机制），当前方案导出时隐藏地图只导文字。教程给出 4 个改进方向：静态地图 API / 分开导出后端合并 / Puppeteer 截图 / 简化内容。
- **终态三态渲染**（升级新增）：`Result.vue` 按 `success / degraded / failed` 三态渲染警告卡；仅存在真实景点坐标时才初始化地图（弃用北京默认中心）；降级空壳不展示行程/地图/编辑/导出，失败展示错误+重试，见 §9.4。

## 5. 与前几章的关系

| 前序章节 | 在本章的体现 |
|---------|------------|
| 第一章 初识智能体 | travel_assistant 原型的完全体重制 |
| 第四章 经典范式 | 多智能体协作思想的工程落地（非 ReAct，而是确定性流水线编排） |
| 第七章 Agent 框架 | 直接复用 `SimpleAgent` + 工具注册机制（`add_tool`/`list_tools`） |
| 第十章 通信协议 | MCP stdio 传输 + 工具自动发现的实战应用（GitHub MCP → 高德 MCP） |
| 第九章 上下文工程 | `_build_planner_query` 就是手工版 Gather+Select：把三方结果组装成规划上下文 |

> ⚠️ 进度提示：教程还有第十二章《智能体性能评估》，本项目按你的指示直接进入第十三章。若之后需要补学评估章，随时说一声即可。

## 6. 本项目实现差异与环境适配

### 6.1 代码来源声明

`chapter13/code/helloagents-trip-planner/` 最初通过 sparse clone 从 hello-agents 仓库原样拉取，并逐一核验了 35 个官方文件。运行验证后保留了以下必要适配：

- `frontend/src/services/api.ts`：~~将 Axios 等待上限从 120 秒放宽到 50 分钟~~（⚠️ 升级后回落到常规 30s timeout——`POST /plan` 立即受理返回 `run_id`，不再长等待；新增 `subscribeRunEvents()` 用 `EventSource` 订阅 SSE 事件流，见 §9.3）；
- `frontend/src/env.d.ts`：声明 `VITE_AMAP_SECURITY_JS_CODE`；
- `frontend/src/views/Result.vue`：在加载高德 JS API 2.0 前，从环境变量注入 `_AMapSecurityConfig.securityJsCode`。

对齐状态：**功能等价（官方示例 + 本地运行环境适配）**。真实 `.env`、`node_modules` 和构建产物均不进入版本控制。

### 6.2 教程正文 vs 代码仓的差异（以代码仓为准）

阅读教程时注意以下不一致，**实际实现以拉取的代码为准**：

| 项目 | 教程正文 | 代码仓实际 |
|------|---------|-----------|
| MCP 启动方式 | `npx @sugarforever/amap-mcp-server` | `uvx amap-mcp-server`（Python 生态，教程 13.4.2 也注明了这一点） |
| MCPTool 参数 | `command=` + `args=[...]` | `server_command=["uvx", "amap-mcp-server"]` |
| 请求模型类名 | `TripPlanRequest` | `TripRequest` |

### 6.3 版本要求（⚠️ 需要你决策）

`backend/requirements.txt` 要求：

```
hello-agents[protocols]>=0.2.4,<=0.2.9
fastapi>=0.115.0, uvicorn[standard], pydantic-settings, httpx, aiohttp,
python-dotenv, python-multipart, loguru, fastmcp>=2.0.0, uv>=0.8.0, python-dateutil, huggingface_hub
```

- 当前 conda 环境 `agent_study` 是 **hello-agents==0.2.2**，**不满足**本章要求区间 `[0.2.4, 0.2.9]`。按项目红线，我不会擅自升级；你确认后我再执行安装（建议先看 6.4 的隔离建议）。
- `fastmcp==2.12.5` 已满足 `>=2.0.0`；`uv`/`uvx` 需确认是否已装（`uvx --version`）。
- 其余 FastAPI 系依赖大概率未装，首次运行需 `pip install -r requirements.txt`（等你授权）。

### 6.4 LLM 配置：Kimi 兼容性（好消息）

`llm_service.py` 用 `HelloAgentsLLM()` 无参构造，它自动读取环境变量 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` —— **与项目根 `.env` 的 Kimi 配置完全同名同义**，无需任何代码改动。两种配置方式任选：

```bash
# 方式A：复用根目录 .env 的 OPENAI_*（Kimi k2.6）
# 方式B：在 backend/.env 里显式写 HelloAgents 变量名
LLM_MODEL_ID=kimi-k2.6
LLM_BASE_URL=https://kimi.a7m.com.cn/v1
LLM_API_KEY=<your_kimi_key>
```

遵循 docs/ENVIRONMENT.md 第 2 节替换规则；Kimi 请求保持最小 `model + messages`，不传 temperature 等参数。

### 6.5 新增凭据需求（三种 Key，均不入库）

| Key | 用途 | 申请地址 | 放在哪 |
|-----|------|---------|--------|
| LLM Key | 已有（Kimi） | — | 根 `.env` 或 `backend/.env` |
| 高德 Web 服务 Key | 后端 MCP POI/天气 | console.amap.com → 应用 → Web服务 | `backend/.env` 的 `AMAP_API_KEY` |
| 高德 Web端(JS API) Key | 前端地图渲染 | console.amap.com → 应用 → Web端(JS API) | `frontend/.env` 的 `VITE_AMAP_WEB_JS_KEY` |
| Unsplash Access Key | 景点配图 | unsplash.com/developers | `backend/.env` 的 `UNSPLASH_ACCESS_KEY` |

注意：**高德的"Web 服务"和"Web端 JS API"是两种不同类型的 Key**，不能混用。Unsplash 为国外免费服务，搜索可能不够准（教程建议生产换国内源）。

## 7. 运行方式

前置：Python ≥3.10、Node.js ≥16、npm ≥8、uv/uvx 可用、上述三种 Key 就绪。

```powershell
# ===== 后端 =====
conda activate agent_study
$env:PYTHONIOENCODING="utf-8"          # Windows 防 GBK 崩溃（框架日志含 emoji）
cd chapter13\code\helloagents-trip-planner\backend
# pip install -r requirements.txt       # 待你授权后执行
Copy-Item .env.example .env             # 填入 AMAP_API_KEY / UNSPLASH_ACCESS_KEY (+可选 LLM_*)
python run.py                           # 或 uvicorn app.api.main:app --reload
# 成功标志: http://localhost:8000/docs 出现 Swagger UI

# ===== 前端（新开终端）=====
cd chapter13\code\helloagents-trip-planner\frontend
# npm install                           # 待你确认后执行
Copy-Item .env.example .env             # 填入 VITE_AMAP_WEB_KEY / VITE_AMAP_WEB_JS_KEY
npm run dev
# 访问 http://localhost:5173

# ===== 冒烟测试路径 =====
# 1. uvicorn 启动日志应打印"景点搜索Agent: N 个工具"（N>0 说明 auto_expand 生效）
# 2. 浏览器填表 → 提交 → 页面秒回 run_id，随后按 SSE 真实步骤推进（搜索景点→查天气→推酒店→生成计划）
# 3. 结果页检查地图标记 / 预算明细 / 导出功能（仅 success/degraded 有可用计划时展示）
# 4. 失败路径：临时断网/断 Key → 页面应如实显示降级/失败与失败清单，而非伪装成功
```

常见坑预警（结合本项目历史教训）：
- `load_dotenv()` 时序：本仓库 `config.py` 已把 `load_dotenv()` 放在模块顶部，符合规范，无需改动；
- Windows 控制台 emoji 日志必须 `$env:PYTHONIOENCODING="utf-8"`；
- MCP 子进程由 uvx 拉起，首次运行会自动下载 `amap-mcp-server` 包，需网络通畅（代理环境留意）；
- CORS 默认放行 `localhost:5173/3000`，前端端口变了要同步 `backend/.env` 的 `CORS_ORIGINS`。

## 8. 学习建议

**建议阅读顺序**（自底向上，与教程 13.2 的建模哲学一致）：
1. `models/schemas.py` → 理解数据契约（对应教程 13.2）
2. `agents/trip_planner_agent.py` → 四 Agent 提示词 + plan_trip 流水线（13.3）+ 共享 MCPTool（13.4）
3. `api/routes/trip.py` → 路由如何串联 Agent 与 Unsplash 增强
4. 前端 `types/index.ts` → `services/api.ts` → `Home.vue` → `Result.vue`（13.5/13.6）

**动手实验方向**（教程结语建议 + 个人扩展）：
- 并行化：景点/天气/酒店三个 Agent 相互独立，用 `asyncio.gather` 并发替代串行，观察耗时变化；
- 把升级的 Run 状态机进一步映射到 LangGraph / OpenAI Agents SDK 的图结构，体会"应用级编排"与"框架级编排"的边界（面试可用，见 §9.5 ADR-0002）；
- 给 Run 增加"持久化历史"能力（当前为零落盘，进程重启即丢失，ADR-0003 已知局限），评估 SQLite/JSONL 的取舍；
- 给 SSE 事件流补充：多客户端并发订阅同一 Run、断线重连历史重放与去重的观察实验（§9.3 工程细节）；
- 新增"餐厅推荐 Agent"或交通路线 Agent（高德 MCP 有路线规划工具），体会分工式架构的扩展成本有多低；
- 尝试教程给出的 4 种导出改进方案之一（如静态地图 API）；
- 对比第一章 `travel_assistant.py` 与本章 `plan_trip`：同一个 TAO 思想在不同复杂度下的形态差异。

**重点思考题**：
1. 为什么 PlannerAgent 不给工具？（答：整合是纯推理任务，给工具反而增加不确定性——职责单一原则）
2. `auto_expand=True` 与第十章手动发现 MCP 工具有什么体验差异？
3. ~~fallback 占位计划是"优雅降级"还是"掩盖错误"？~~（升级后答案已定型：见 §9.5 ADR-0001——兜底保留但必须**显式标注为降级**，未标注的降级不算 graceful；可运行性优先但绝不伪装成功）什么场景下应该改成快速失败？（答：当降级数据可能误导决策、或成功路径收益小于失败成本时）

---

## 9. Agent 运行时升级（Run 状态机 / SSE 真实进度 / 显式降级）

> 本节是对 4.x「五步协作流水线」之上的一层**应用级 Run 编排外壳**的说明。它不动 Agent 内核（仍保留 `SimpleAgent` + 高德 MCP），只解决一个核心问题：**让一个"能跑通但不可信"的演示，变成"能讲明白的现代 Agent 系统"**——真实状态、真实进度、失败可见、数据可信。这是求职作品集的叙事主线，面试时按本节三张图讲述。
>
> 相关决策已固化在 `chapter13/docs/adr/0001-0003`，术语见 `chapter13/CONTEXT.md`。

### 9.1 问题：旧实现的"不可信"在哪

升级前的助手是一个单一方法内固定顺序的 4 步调用，有三处会被面试官质疑的硬伤：

| 缺陷 | 表现 |
|------|------|
| **伪造兜底** | 任意一步失败都吞掉错误，为任何城市生成以**北京为基准的假坐标**与占位景点，API 恒定 `success=True`，用户无法分辨真实数据与降级数据 |
| **假进度** | 前端进度条是计时器模拟的，最坏要干等 50 分钟；LLM 自动重试期间用户只看到"生成中" |
| **错城市图片** | 景点图片搜不到时默认展示北京天坛照片，与目的地毫无关系 |

升级目标：**可运行性优先，但失败必须诚实可见、数据必须可信**。核心手段是把一次请求建模为一个带唯一 `run_id` 的 **Run**，赋予它显式状态机、真实事件流和三态终局。

### 9.2 Run 状态机（第一张图）

一次旅行请求对应一个 Run，生命周期由 `pending → running → success | degraded | failed` 五态组成，终态三态。状态与事件流**驻留进程内存**（`runtime/registry.py`），进程退出即丢失（ADR-0003 零落盘约定）。

```
  POST /api/trip/plan        后台执行（独立线程池）        终态判定
  （请求层校验通过）                                        runner.py
  ┌─────────────┐    受理     ┌─────────────┐   warnings 为空   ┌─────────────┐
  │   pending   │ ─────────▶ │   running   │ ────────────────▶ │   success    │
  │ 创建Run+通道 │   创建任务   │ 编排四步+推送  │  result 完整       │   result     │
  │ 立即返回202 │             │ 真实事件      │                  │  warnings=[] │
  └─────────────┘             └──────┬──────┘                  └─────────────┘
                                     │ warnings 非空（触发降级）
                                     │  plan = 空壳计划 + warnings
                                     ▼                        ┌─────────────┐
                               ┌─────────────┐  依赖构造/执行    │             │
                               │   degraded  │                 │   failed    │
                               │ result=空壳 │                 │ result=null │
                               │ +warnings   │  抛异常  ─────▶ │ +warnings   │
                               └─────────────┘                 │ +error      │
                                                               └─────────────┘
```

三个终态的判定逻辑（`runner.py::run` + `schemas.PlanningOutcome`）：

- **success**：`warnings` 为空，返回完整 `TripPlan`。
- **degraded**：`warnings` 非空（某搜索步骤失败/空结果/schema 校验失败/隔离了可疑输入），返回一个**空壳计划**（`days=[] / weather_info=[] / budget=null`，仅保留请求中的 city/日期）+ 失败清单。**绝不含虚构坐标**。
- **failed**：依赖构造或执行抛异常（如最终规划重试耗尽 `FinalPlanError`），不产生 result，携带 `error` 与 `warnings`，**不伪装成功**。

### 9.3 SSE 真实事件流（第二张图）

`POST /plan` 只做**受理**——立即返回 `run_id`（HTTP 202），计划在后台执行。前端用 `EventSource` 订阅 `GET /api/trip/runs/{run_id}/events`，收到六类类型化事件，按真实步骤渲染。`events.py` 定义了协议，`trip.py::stream_run_events` 实现历史重放 + 实时追加 + 心跳保活。

```
 浏览器 (EventSource)          FastAPI /trip 路由                    后台执行器 (runner)
        │  POST /api/trip/plan      │                          │
        │◄──────── 202 + run_id ────┤  registry.create + 创建任务│
        │  GET /runs/{id}/events    │                          │ asyncio task
        │◄────── SSE 事件流 ────────┤                          │
        │                          │  ←── publish(run_started)  │ transition(running)
        │  event: run_started       │                          │
        │                          │  ←── publish(step_started) │ _run_search_step ×3
        │  event: step_started(景点)│                          │
        │  event: tool_call        │  ←── publish(tool_call)    │ EventEmittingAmapTool
        │  event: tool_result      │  ←── publish(tool_result)  │ 工具实际执行
        │  event: step_started(计划)│                          │ plan_final_with_retry
        │  event: run_completed    │  ←── publish(run_completed)│ transition(终态)
        │  : keepalive (10s 心跳)   │                          │ close_channel
```

| 事件类型 | 载荷要点 | 触发时机 |
|----------|---------|---------|
| `run_started` | status / city / travel_days | Run 进入 running（第 9.2 图左） |
| `step_started` | step / label / city | 编排四步（景点/天气/酒店/计划）各自开始 |
| `tool_call` | tool_name / parameters | 高德工具实际执行前 |
| `tool_result` | tool_name / result_preview 或 error | 工具执行完成 |
| `validation_error` | step / error | 中间结果 schema 校验失败（如"返回空结果/字段缺失"，见 §9.4 失败分支） |
| `run_completed` | status / warnings / result / error | 到达终态 |

工程细节（都可作为面试论述点）：
- **历史重放**：`RunEventChannel.snapshot()` 让迟到订阅 / 断线重连先收到完整历史，再进入实时流；前端用 `run_id + timestamp + type` 签名去重，避免 replay 重复触发 UI 副作用。
- **线程模型**：`SimpleAgent.run()` 是同步阻塞调用，移入独立 `planner_executor`（有界线程池）不阻塞事件循环；SSE 空闲等待走独立 `sse_executor`，两个池互不抢占——长时间空闲的订阅者不会拖慢后续 Run 的受理与执行（`factory.py`）。
- **心跳保活**：SSE 通道 `wait_next` 带超时预算，窗口内无新事件时发注释行 `: keepalive` 维持连接，不无限阻塞。

### 9.4 失败与降级语义（第三张图）

升级的核心原则：**失败走显式路径，绝不伪造成功**。三张图合起来回答"系统失败时到底做了什么"——这是区分"demo"与"作品集"的关键。

```
                                  规划流水线 plan_trip（四步顺序执行）
        ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌──────────────┐
        │ ①景点搜索    │ ──▶ │ ②天气查询    │ ──▶ │ ③酒店搜索    │ ──▶ │ ④生成行程计划 │
        └──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬───────┘
   每步输出经   │                   │              │              │           │
   Pydantic 校验│ 类型化中间结果      │              │              │     最终规划有界重试
               │ (models/intermediates)         │              │      (3次, 0.1s→0.2s)
               ▼                               ▼                          ▼
      ┌──────────────────┐              ┌──────────────┐          失败分支C
      │   失败分支A        │              │  失败分支B     │          模型输出 schema 非法
      │  ①工具失败/空结果   │     ┌──────▶ │  schema 校验   │          重试耗尽 → 抛 FinalPlanError
      │  ②注入隔离         │     │        │  失败（会发     │          → runner 落 failed
      │  各自记入 warnings │     │        │  validation_  │
      │（不再进入规划提示词）│     │        │  error 事件）  │
      └──────────────────┘     │        └──────────────┘
               │                │                  │
               └────────────────┴──────────────────┘
                      任一失败分支都不吞错：
           要么带 warnings 继续 → 空壳 → degraded；要么抛 → failed；全绿 → success
```

- **每步独立重试**：单步工具失败只影响该步，不拖垮已完成步骤；已固化的搜索中间结果（类型化对象）不因最终规划重试而重跑——重试范围**只限规划器本身**。
- **"先失败后成功"也不吞错**：即便步骤最终产出类型化结果，其内发生过的工具失败证据（`ToolFailureRecorder`）仍写入 warnings，由调用方判定是否降级——不做"最终成功就假装一切顺利"的掩盖。
- **显式降级产物**：任一搜索步骤失败 → 返回空壳计划并标记 `degraded`，页面如实渲染失败清单；不进入规划提示词，不会用北京坐标冒充目的地。
- **不可信输入隔离**：用户自由文本与工具返回按不可信数据处理——命中指令注入标记（覆盖/泄露/system prompt/工具调用语法）的条目整体隔离、不进规划提示词并记入 `warnings`（`input_isolation.py`），恶意输入最多触发 `degraded`，绝不污染规划。
- **图片兜底中性化**：`GET /api/poi/photo` 未命中/异常一律 HTTP 200 + `is_placeholder=true` + `warnings`；前端渲染中性 SVG 占位图（标注"示意图"），删除了"默认天坛照片"的错城市兜底。
- **请求层快速拒绝**：日期格式、`start_date/end_date/travel_days` 一致性等交叉校验在 API 层完成，非法输入直接 422，不浪费一次无效的 Agent 运行（评测集样例 2 的依据）。

### 9.5 设计权衡（ADR 结论，面试论述素材）

| ADR | 结论 | 一句话论述 |
|-----|------|-----------|
| **0001** 显式降级 | 兜底保留，但必须标注降级 | 可运行性优先于局部数据真实性，但**不伪装成功**——失败清单是响应的一等公民 |
| **0002** 不做通用抽象 | 升级以"可运行 + 可讲明白"为准绳 | 不引入 LangGraph：面试时用"状态模型可映射到图结构"的论述替代真实适配器，抽象层代码讲不成亮点 |
| **0003** 零落盘 | Run 状态驻留进程内存 | 后台执行+真实进度+显式失败语义已由内存 registry 满足；数据库/JSONL 只会引入生命周期与写盘复杂度 |

**已知局限（面试时主动陈述更显诚实）**：进程重启丢失进行中/已完成 Run；无法在应用内重放历史运行；多进程部署时各进程 registry 相互独立（当前单进程演示场景接受）。

### 9.6 评测与验证

- **5 条黄金评测集**（`backend/tests/evaluation/scenarios/01..05`）全部走**同一条公开 HTTP 缝**（FastAPI TestClient + 注入桩运行时）：happy path 上海 3 天、缺日期字段 422、搜索空结果降级、schema 非法重试耗尽显式 failed、恶意输入隔离。
- **离线评测 CLI**：`python -B evaluate.py` 逐条 `PASS/FAIL`: reason + SUMMARY，退出 0/1/2；默认桩离线可跑、零写盘（`offline_guard.py` 用 audithook 证明无写文件/文件树变更/external socket/子进程派生）。
- **真实 Key 快乐路径**：`--real --case happy_path` 经预检后走同一 HTTP 缝校验真实 success 结构；不做静默回退。
- 全量回归：`python -B -m unittest discover -s tests` → **73/73 OK**。

> ⚠️ 环境相关：运行前 `load_dotenv()` 先于 `hello_agents` 导入；Windows 控制台设 `$env:PYTHONIOENCODING="utf-8"`；Kimi 请求保持最小 `model + messages`。

---

*学习阶段产物：本 README + 官方示例代码。NOTES.md 将在你宣布"完成第十三章"后生成。*
