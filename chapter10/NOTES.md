# 第十章学习笔记：智能体通信协议

> **完成时间**: 2026-08-25
> **教程**: [Hello-Agents 第十章 智能体通信协议](https://github.com/datawhalechina/hello-agents/blob/main/docs/chapter10/%E7%AC%AC%E5%8D%81%E7%AB%A0%20%E6%99%BA%E8%83%BD%E4%BD%93%E9%80%9A%E4%BF%A1%E5%8D%8F%E8%AE%AE.md)
> **框架版本**: hello-agents 0.2.2（fastmcp 2.12.5 / mcp 1.16.0 / authlib 1.7.2）

---

## 1. 核心收获

### 1.1 MCP：智能体与工具的标准化通信

MCP（Model Context Protocol，Anthropic 提出）解决"智能体如何标准地调用外部工具"的问题，核心设计理念是**上下文共享**，不仅是 RPC 协议，更强调智能体与工具之间共享丰富的上下文信息。

**三层架构**：

| 层级 | 角色 | 职责 |
|------|------|------|
| **Host（宿主层）** | LLM 应用（如 Claude Desktop） | 接收用户输入，与 LLM 交互，管理对话流程 |
| **Client（客户端层）** | Host 内置的 MCP 客户端 | 与 MCP Server 建立连接，发送请求，接收响应 |
| **Server（服务器层）** | 具体功能提供者 | 执行实际的文件操作、API 调用等 |

**三大核心能力**：

- **Tools（工具）**：可被 LLM 调用的函数，主动执行操作
- **Resources（资源）**：供 LLM 读取的结构化数据，被动提供信息
- **Prompts（提示模板）**：预定义的提示词模板，指导性内容

**传输方式**：当前 MCP 规范将 **Stdio**（本地开发，通过标准输入输出与子进程通信）和 **Streamable HTTP**（生产环境、远程服务）作为主要传输方式，SSE 已标记为遗留（legacy）。教程中 `MCPTool` 的五种传输模式（Memory、Stdio、HTTP、SSE、StreamableHTTP）是 HelloAgents/FastMCP 框架的**封装抽象**，用于简化教学。

**Function Calling 与 MCP 的关系**：两者不是竞争关系，而是相辅相成。Function Calling 是 LLM 的**核心能力**（模型理解何时调用函数并精准生成参数），MCP 是**基础设施协议**（在工程层面标准化工具如何被描述和调用）。类比：Function Calling 是"学会如何打电话"（技能），MCP 是"全球统一的电话通信标准"（协议）。

### 1.2 A2A：智能体之间的点对点协作

A2A（Agent-to-Agent Protocol，Google 提出）与 MCP 关注智能体与工具不同，关注**智能体之间如何像人类团队一样协作**。设计哲学是**对等通信**：每个智能体既是服务提供者，也是服务消费者，避免中心化协调器的瓶颈。

核心概念：

- **Agent Card**：智能体的"名片"，描述能力、端点、认证方式
- **Task（任务）**：智能体之间的基本工作单元，有明确生命周期（创建 -> 协商 -> 代理 -> 执行中 -> 完成/失败）
- **Artifact（工件）**：任务执行过程中产生的输出产物

A2A 请求生命周期四步：代理发现（Agent Discovery）→ 身份验证 → 发送消息 API → 发送消息流 API。

### 1.3 ANP：大规模智能体网络的服务发现

ANP（Agent Network Protocol）是开源社区维护的概念性协议框架，核心设计理念是**去中心化服务发现**：在包含成百上千个智能体的网络中动态发现所需服务，无需预先配置所有连接关系。

**重要定位**：本章的 ANP 实现（`ANPDiscovery`、`register_service`、`discover_service` 等）是 HelloAgents 框架的**概念性/轻量级实现**：所有服务注册和发现都在同一进程内的内存对象中完成，没有网络通信、持久化和容错机制，**不能用于生产环境**。生产参考是 [AgentConnect](https://github.com/agent-network-protocol/AgentConnect)。

### 1.4 HelloAgents 三层协议架构

```
智能体集成层（Agent Integration Layer）: Agent 通过 Tool System 使用协议工具
    ↓
工具封装层（Tool Wrapper Layer）: MCPTool / A2ATool / ANPTool 统一 run() 接口
    ↓
协议实现层（Protocol Implementation Layer）: FastMCP 客户端/服务器、a2a-sdk、自研 ANP
```

核心设计：三种协议实现被封装成统一的 `Tool` 接口，Agent 用调用普通工具的方式使用协议工具，无需关心底层协议细节。其中 `MCPTool` 的**自动展开机制**最值得理解：连接服务器 → `list_tools()` 发现工具 → 为每个工具创建 `{name}_{tool_name}` 格式的包装器 → 注册到 ToolRegistry。

---

## 2. 实践记录

### 2.1 环境

- 当前解释器实测 `hello-agents 0.2.2`，协议依赖 `fastmcp 2.12.5` / `mcp 1.16.0` / `authlib 1.7.2`。
- 本章不重复安装依赖；运行社区 MCP 服务器需要 Node.js/npx。

### 2.2 运行时验证（仅此一项）

**`03_GitHubMCP.py`**（使用社区 `@modelcontextprotocol/server-github` MCP 服务器）：

- 成功发现 **26 个 GitHub 工具**（通过 `list_tools`）。
- 调用 `search_repositories` 返回**有效的仓库搜索结果**（查询 `AI agents language:python`）。
- 程序退出时出现 `unclosed transport` / `Event loop is closed` 清理告警，但业务调用已完整完成，且检查时**没有残留 `server-github` Node 进程**，因此判定为非致命的 asyncio 子进程回收告警，不是 MCP 调用失败。

### 2.3 静态验证（非运行时）

- `chapter10/code/` 目录共 **23 个 Python 文件**（含 `weather-mcp-server/server.py`），全部通过 AST 语法解析。
- 其余示例（`01_TestConnect.py`、`02_Connect2MCP.py`、`04_MCPTransport.py`、`05_UseMCPToolInAgent.py`、`07_SimpleA2AAgent.py`、`09_A2A_WithAgent.py`、`11_ANPInit.py` 等）**仅做了代码阅读与静态检查，未实际运行**，本章不声明它们的运行结果。

---

## 3. Bug 修复记录

### Bug 1: 源码 docstring 中泄漏 GitHub Token（安全修正）

- **问题**：`03_GitHubMCP.py` 的模块 docstring 中曾嵌入一个**真实的 GitHub Personal Access Token**，随代码落在源码里。
- **修复**：已将 docstring 中的真实 token 替换为占位符 `your_token_here`，运行时不依赖该占位符，改为从环境变量 `GITHUB_PERSONAL_ACCESS_TOKEN` 读取。
- **遗留事项**：已泄漏的 token 仍可能在历史记录/已提交内容中可查，**需要在 GitHub 上撤销（revoke）或轮换（rotate）该 token**，不能仅靠改源码了事。

### Bug 2: `unclosed transport` / `Event loop is closed` 关闭告警

- **现象**：运行 `03_GitHubMCP.py` 退出时出现该告警。
- **定位**：这是 asyncio 的 stdio 子进程传输在事件循环关闭时的回收告警，属于**非致命**的清理噪音。
- **证据**：业务结果（工具发现 + 仓库搜索）均已完成，且检查时无 `server-github` Node 进程残留。
- **跟踪**：若后续出现进程残留或结果不完整，再单独排查客户端关闭时序，当前不视为失败。

### Bug 3: `load_dotenv()` 时序适配

- **现象/根因**：沿用 Chapter 9 的经验（MEMORY.md 8.8），部分 `hello_agents` 模块在导入时即创建/缓存配置对象并读取环境变量；若 `load_dotenv()` 在导入之后调用，缓存对象不会刷新。
- **修复**：在 `03_GitHubMCP.py` 和 `09_A2A_WithAgent.py` 中把 `load_dotenv()` 放到所有 `hello_agents` 导入**之前**，作为本项目环境适配。

---

## 4. 代码对齐差异

| 项目 | 教程写法 | 本项目 | 对齐状态 |
|------|----------|--------|----------|
| 示例来源 | 官方仓库 commit `45dd84e626a91997294ac8d4d44f18b29a411c6e` | 本章代码与上游保持一致 | 已对齐（仅最小环境/安全适配） |
| 框架版本 | hello-agents 0.2.2 | 0.2.2（2026-08-25 实测） | 已对齐 |
| 协议依赖 | 随 protocol extra 安装 | fastmcp 2.12.5 / mcp 1.16.0 / authlib 1.7.2 | 功能等价 |
| 模型 | GPT 系列 | Kimi（`.env` 的 `OPENAI_*` 配置，`HelloAgentsLLM()` 自动读取） | 功能等价 |
| `load_dotenv()` 时序 | 未特别强调 | 置于所有 `hello_agents` 导入之前 | 环境适配 |
| Token 处理 | docstring 中曾含真实值 | 替换为 `your_token_here` 占位符 | 安全适配 |

**版本提醒**：Chapter 9 记录的 `0.2.8` 是当时的历史环境基线，**不代表本章实际版本**；本章当前解释器报告 `hello-agents 0.2.2`。遇到不兼容时以 `pip show hello-agents` 核对的真实版本为准，不要主动升级或降级。

**验证范围澄清**：本章对 23 个 Python 文件做了 **AST 语法解析级别的静态验证**（确认语法正确、可被解析），但对除 `03_GitHubMCP.py` 外的示例**未做运行时执行验证**。代码阅读/静态检查与运行时验证是两种不同层级的工作，本章不以静态检查冒充运行时验证。

---

## 5. 深度思考

1. **MCP 解决的是"工具生态复用"问题**。此前每接一个新服务都要手写 Tool 类，MCP 把工具描述、调用、发现都标准化，社区服务器（如 `server-filesystem`、`server-github`）开箱即用。教程的 `03_GitHubMCP.py` 只写了几行就拿到 26 个 GitHub 工具，是协议标准化价值的直观体现。
2. **Function Calling 与 MCP 是分层关系而非替代关系**。模型侧的"会调用函数"能力与工程侧的"如何描述和连接工具"标准，分别解决不同层级的问题，缺一不可。
3. **A2A 的 Task/Artifact 抽象与 MCP 的工具调用模型本质不同**。MCP 是"请求-响应"式的工具调用，A2A 是"任务生命周期"式的对等协作，后者天然适合多智能体分工与协商。`09_A2A_WithAgent.py` 用 `threading` 后台启动 A2A 服务、再把对端封装成 Tool 喂给 `SimpleAgent` 的 MCP+A2A 混合模式，是理解两类协议如何协同的关键案例（仅静态阅读）。
4. **传输方式要与框架抽象区分对待**。教程展示的五种传输是简化教学的封装，当前 MCP 官方规范只把 Stdio 和 Streamable HTTP 当主力、SSE 已遗留。做真实项目时应以官方规范为准，别被教程的五种模式误导。
5. **ANP 仍停留在概念演示阶段**。进程内内存的服务注册/发现无法支撑真实网络规模的智能体网络，这是生态不成熟的表现。理解其"服务发现 + 负载均衡决策（`metadata.load` 等）"的思想即可，生产化需看 AgentConnect 等社区方案。
6. **安全永远是第一优先级**。本次把真实 GitHub token 从 docstring 中清除是必要的，但泄漏 token 的撤销/轮换才是收尾，且今后任何凭据都只走环境变量。

---

## 6. 下一步计划

1. **撤销/轮换泄漏的 GitHub token**（Bug 1 遗留事项，需在 GitHub 设置中操作）。
2. **实际运行 `02_Connect2MCP.py`（文件系统服务器）和 `05_UseMCPToolInAgent.py`（自动展开机制）**，与静态阅读结论互相印证。
3. **运行 A2A 系列（`07_SimpleA2AAgent.py`、`09_A2A_WithAgent.py`）**，验证 A2AServer + 线程 + Tool 封装 + SimpleAgent 的混合集成；需要确认 `a2a-sdk` 依赖是否就绪。
4. **用 `my_mcp_server.py` 自定义 MCP 服务器**（FastMCP 的 `@mcp.tool` / `@mcp.resource` / `@mcp.prompt`），观察自定义工具在 Agent 中的自动展开。
5. **了解生产级 ANP 生态**（AgentConnect），对比本章概念实现与真实服务发现的差距。
