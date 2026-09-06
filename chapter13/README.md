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
- **fallback 计划**：任何一步失败都不让请求 500，而是生成占位行程保证前端可渲染。生产取舍：可用性 > 数据真实性。

### 4.2 提示词即契约

四个 PROMPT 常量就是四个 Agent 的全部"人格"。以规划专家为例，它要求 LLM 严格按 JSON Schema 返回（温度纯数字不带 °C、每天 2-3 景点、必含三餐、必含 budget）。**Pydantic 模型 + 提示词中的 JSON 示例 + 解析降级**三者构成完整的输出可靠性链条。

### 4.3 前端的工程细节（Result.vue）

- **Axios timeout=3000000**：四 Agent 串行调用叠加 LLM 自动重试，实测可能超过官方默认的 120 秒；当前学习环境将前端等待上限放宽至 50 分钟，后续优化并发与重试策略后应再收紧；
- **模拟进度条**：`setInterval` 每 500ms 推进进度并切换状态文案（搜索景点→查天气→推酒店→生成计划），解决长等待的用户焦虑；
- **编辑模式的深拷贝**：`originalPlan = JSON.parse(JSON.stringify(tripPlan))`，取消编辑可回滚；移动景点用 ES6 解构交换 `[a[i],a[j]]=[a[j],a[i]]`；保存后重新 `initMap()` 同步标记；
- **导出的已知局限**：html2canvas 无法处理高德地图的嵌套 Canvas（跨域+渲染机制），当前方案导出时隐藏地图只导文字。教程给出 4 个改进方向：静态地图 API / 分开导出后端合并 / Puppeteer 截图 / 简化内容。

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

- `frontend/src/services/api.ts`：将 Axios 等待上限从 120 秒放宽到 50 分钟，避免多智能体串行调用和 LLM 自动重试期间前端提前断开；
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
# 2. 浏览器填表 → 开始规划 → 观察 backend 控制台四步日志（📍→🌤️→🏨→📋）
# 3. 结果页检查地图标记 / 预算明细 / 导出功能
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
- 新增"餐厅推荐 Agent"或交通路线 Agent（高德 MCP 有路线规划工具），体会分工式架构的扩展成本有多低；
- 把模拟进度条升级为 SSE/WebSocket 真实进度推送；
- 尝试教程给出的 4 种导出改进方案之一（如静态地图 API）；
- 对比第一章 `travel_assistant.py` 与本章 `plan_trip`：同一个 TAO 思想在不同复杂度下的形态差异。

**重点思考题**：
1. 为什么 PlannerAgent 不给工具？（答：整合是纯推理任务，给工具反而增加不确定性——职责单一原则）
2. `auto_expand=True` 与第十章手动发现 MCP 工具有什么体验差异？
3. fallback 占位计划是"优雅降级"还是"掩盖错误"？什么场景下应该改成快速失败？

---

*学习阶段产物：本 README + 官方示例代码。NOTES.md 将在你宣布"完成第十三章"后生成。*
