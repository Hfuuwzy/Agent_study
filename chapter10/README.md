# 第十章 智能体通信协议

> [!info] 学习概览
> **目标**: 理解 MCP、A2A、ANP 三种智能体通信协议的核心设计理念与实践
> **实践**: 连接 MCP 服务器、在 Agent 中使用 MCP 工具、搭建 A2A 智能体、体验 ANP 服务发现
> **重点**: MCP 的 Host/Client/Server 三层架构、Tools/Resources/Prompts 三大核心能力、A2A 的 Task/Artifact 抽象、ANP 的服务发现机制

---

## 1. 本章定位

本章在前九章的基础上，从**单体智能体**迈向**互联智能体**。第七章构建了 ReAct 智能体的核心循环，第八章引入了记忆系统，第九章优化了上下文利用。但单体智能体始终面临三个根本限制：

1. **工具集成困境** -- 每接入一个新服务（GitHub、数据库、文件系统）都要手写 Tool 类，无法复用社区成果。
2. **能力扩展瓶颈** -- 智能体只能使用预先定义好的工具集，无法动态发现新服务。
3. **协作缺失** -- 多个专业智能体之间无法直接对话，只能靠手动编排。

**通信协议**解决的就是这些问题。它提供标准化的接口规范，就像互联网的 TCP/IP 协议让不同设备互通一样，通信协议让智能体、工具、服务之间以统一的方式互联。

**本章引入三种协议**：

| 协议 | 全称 | 发起方 | 解决的核心问题 |
|------|------|--------|----------------|
| **MCP** | Model Context Protocol | Anthropic | 智能体与工具的标准化通信 |
| **A2A** | Agent-to-Agent Protocol | Google | 智能体之间的点对点协作 |
| **ANP** | Agent Network Protocol | 开源社区 | 大规模智能体网络的服务发现 |

---

## 2. 核心概念

### 2.1 三种协议设计理念

#### MCP -- 智能体的"USB-C"

MCP 统一了智能体与外部工具的交互方式。无论你使用 Claude、GPT 还是其他模型，只要它们支持 MCP 协议，就能无缝访问相同的工具和资源。

**核心设计理念**: 上下文共享。MCP 不仅仅是 RPC 协议，更重要的是它允许智能体和工具之间共享丰富的上下文信息。

**三层架构**:

| 层级 | 角色 | 职责 |
|------|------|------|
| **Host（宿主层）** | LLM 应用（如 Claude Desktop） | 接收用户输入，与 LLM 交互，管理对话流程 |
| **Client（客户端层）** | Host 内置的 MCP 客户端 | 与 MCP Server 建立连接，发送请求，接收响应 |
| **Server（服务器层）** | 具体功能提供者 | 执行实际的文件操作、API 调用等 |

**完整交互流程**:

```
用户问题 -> Host(LLM应用) -> LLM分析 -> 需要外部信息 -> MCP Client -> MCP Server -> 执行操作 -> 返回结果 -> LLM生成回答 -> 显示给用户
```

**三大核心能力**:

| 能力 | 说明 | 类比 |
|------|------|------|
| **Tools（工具）** | 可被 LLM 调用的函数 | 主动执行操作 |
| **Resources（资源）** | 供 LLM 读取的结构化数据 | 被动提供信息 |
| **Prompts（提示模板）** | 预定义的提示词模板 | 指导性的模板 |

**Function Calling 与 MCP 的关系**:

Function Calling 是 LLM 的一项**核心能力** -- 模型理解何时需要调用函数，并精准生成调用参数。MCP 是**基础设施协议** -- 在工程层面解决工具与模型如何连接的问题。两者不是竞争关系，而是相辅相成：

- Function Calling = "学会如何打电话"（技能）
- MCP = "全球统一的电话通信标准"（协议）

**传输方式**:

| 传输方式 | 适用场景 | 说明 |
|----------|----------|------|
| **Stdio** | 本地开发、调试 | 通过标准输入输出与子进程通信 |
| **Streamable HTTP** | 生产环境、远程服务 | 当前 MCP 规范推荐的远程传输方式 |
| SSE (Server-Sent Events) | 实时通信 | **MCP 规范中的 SSE 已视为遗留（legacy）方式**，新项目应优先使用 Streamable HTTP |
| Memory | 单元测试、快速原型 | 进程内传输，无需网络 |

> **重要说明**: 当前 MCP 规范（2026-07-28）将 stdio 和 Streamable HTTP 作为主要传输方式。SSE 虽仍支持但已标记为遗留。**教程中 MCPTool 的五种传输模式（Memory、Stdio、HTTP、SSE、StreamableHTTP）是 HelloAgents/FastMCP 框架的封装抽象**，用于简化学习。实际项目开发时，应参考 MCP 官方规范的最新传输建议。

#### A2A -- 智能体间的对话

A2A 由 Google 提出，其核心设计理念是**实现智能体之间的点对点通信**。与 MCP 关注智能体与工具的通信不同，A2A 关注的是智能体之间如何像人类团队一样协作。

**设计哲学**: 对等通信。每个智能体既是服务提供者，也是服务消费者，避免了中心化协调器的瓶颈。

**核心概念**:

| 概念 | 说明 |
|------|------|
| **Agent Card** | 智能体的"名片"，描述其能力、端点、认证方式等 |
| **Task（任务）** | 智能体之间的基本工作单元，有明确的生命周期 |
| **Artifact（工件）** | 任务执行过程中产生的输出产物 |

**A2A 任务生命周期**:

```
创建 -> 协商 -> 代理 -> 执行中 -> 完成/失败
```

**A2A 请求生命周期**（四个步骤）:

1. 代理发现（Agent Discovery）
2. 身份验证（Authentication）
3. 发送消息 API（Send Message API）
4. 发送消息流 API（Send Message Streaming API）

#### ANP -- 智能体网络的基础设施

ANP 是一个概念性的协议框架，由开源社区维护，**目前还没有成熟的生态**。其核心设计理念是**构建大规模智能体网络的基础设施**。

**设计哲学**: 去中心化服务发现。在一个包含成百上千个智能体的网络中，让智能体能够动态发现所需的服务，而不需要预先配置所有连接关系。

> **重要说明**: 本章的 ANP 实现是 HelloAgents 框架的**概念性/轻量级实现**，用于演示服务发现、注册和负载均衡的核心思想。它不是一个成熟的、可投入生产的协议实现。实际的 ANP 生态可以参考 [AgentConnect](https://github.com/agent-network-protocol/AgentConnect)，但教程仅做概念模拟。

### 2.2 HelloAgents 三层通信协议架构

```
┌─────────────────────────────────────────────────────┐
│              智能体集成层 (Agent Integration Layer)      │
│   ReActAgent / SimpleAgent / ... 通过 Tool System 使用   │
│   协议工具，无需关心底层协议细节                          │
├─────────────────────────────────────────────────────┤
│               工具封装层 (Tool Wrapper Layer)            │
│   MCPTool / A2ATool / ANPTool 继承自 BaseTool，         │
│   提供统一的 run() 接口                                  │
├─────────────────────────────────────────────────────┤
│               协议实现层 (Protocol Implementation Layer)  │
│   MCP: FastMCP 客户端/服务器                              │
│   A2A: 基于 a2a-sdk 的客户端/服务器                        │
│   ANP: 自研轻量级服务发现/注册                              │
└─────────────────────────────────────────────────────┘
```

**各层职责**:

1. **协议实现层**: 包含三种协议的具体实现。MCP 基于 FastMCP 库，A2A 基于 Google 官方的 a2a-sdk，ANP 是自研的轻量级实现。
2. **工具封装层**: 将协议实现封装成统一的 Tool 接口。MCPTool、A2ATool、ANPTool 都提供一致的 `run()` 方法，让智能体以相同的方式使用不同的协议。
3. **智能体集成层**: 智能体与协议的集成点。所有智能体通过 Tool System 来使用协议工具，无需关心底层协议细节。

---

## 3. 架构与目录结构

### 3.1 教程模块结构

```
hello_agents/
├── protocols/                          # 通信协议模块
│   ├── mcp/                            # MCP协议实现
│   │   ├── client.py                   # MCP客户端（支持5种传输方式）
│   │   ├── server.py                   # MCP服务器（FastMCP封装）
│   │   └── utils.py                    # 工具函数
│   ├── a2a/                            # A2A协议实现
│   │   └── implementation.py           # A2A服务器/客户端（基于a2a-sdk）
│   └── anp/                            # ANP协议实现
│       └── implementation.py           # ANP服务发现/注册（概念性实现）
└── tools/builtin/
    └── protocol_tools.py               # 协议工具包装器（MCPTool/A2ATool/ANPTool）
```

### 3.2 本章代码文件清单

以下所有代码文件来自官方仓库 [datawhalechina/hello-agents](https://github.com/datawhalechina/hello-agents) commit `45dd84e626a91997294ac8d4d44f18b29a411c6e`。

**MCP 协议系列**:

| 文件名 | 内容 | 优先级 |
|--------|------|--------|
| `01_TestConnect.py` | 三种协议快速体验（MCP + ANP + A2A） | 第1个阅读 |
| `02_Connect2MCP.py` | MCPClient 连接服务器、发现工具、调用工具 | 第2个阅读 |
| `03_GitHubMCP.py` | 使用社区 GitHub MCP 服务 | 可选 |
| `04_MCPTransport.py` | 五种传输方式演示 | 第3个阅读 |
| `05_UseMCPToolInAgent.py` | MCPTool 在 Agent 中的自动展开机制 | 第4个阅读 |
| `06_MultiAgentDocumentAssist.py` | 多 Agent 协作的智能文档助手 | 第5个阅读 |
| `my_mcp_server.py` | 自定义 MCP 服务器示例（FastMCP） | 配套参考 |
| `14_weather_mcp_server.py` | 天气查询 MCP 服务器 | 第6个阅读 |
| `14_weather_agent.py` | 在 Agent 中使用天气 MCP 服务器 | 第7个阅读 |
| `14_test_weather_server.py` | 测试天气 MCP 服务器 | 配套使用 |
| `weather-mcp-server/` | 天气 MCP 服务器完整项目目录 | 进阶参考 |

**A2A 协议系列**:

| 文件名 | 内容 | 优先级 |
|--------|------|--------|
| `07_SimpleA2AAgent.py` | 创建简单的 A2A 计算器智能体 | 第8个阅读 |
| `08_CustomA2AAgent.py` | 自定义 A2A 智能体 | 第9个阅读 |
| `09_A2A_Server.py` | A2A 服务器实现 | 第10个阅读 |
| `09_A2A_Client.py` | A2A 客户端实现 | 第11个阅读 |
| `09_A2A_Network.py` | A2A 网络通信 | 第12个阅读 |
| `09_A2A_WithAgent.py` | A2A + SimpleAgent 集成案例 | 第13个阅读 |
| `10_A2ATool_Simple.py` | A2ATool 简单封装 | 第14个阅读 |
| `10_AgentNegotiation.py` | Agent 间协商演示 | 第15个阅读 |
| `10_CustomerService.py` | 客服机器人 A2A 应用 | 第16个阅读 |

**ANP 协议系列**:

| 文件名 | 内容 | 优先级 |
|--------|------|--------|
| `11_ANPInit.py` | ANP 服务发现与注册初始化 | 第17个阅读 |
| `12_ANPTaskDistribution.py` | ANP 任务分发 | 第18个阅读 |
| `13_ANPLoadBalancing.py` | ANP 负载均衡 | 第19个阅读 |

**辅助文件（已提交于仓库）**:

| 文件名 | 内容 |
|--------|------|
| `.env.example` | 环境变量模板（`OPENAI_*` + GitHub Token） |
| `my_README.md` | 示例文档（供 MCP 文件系统服务读取测试） |

**运行时生成文件（仅示例运行后才会出现，当前目录中不存在）**:

| 文件名 | 内容 |
|--------|------|
| `output.txt` | 示例输出文件（运行相关示例后生成） |
| `report.md` | 文档助手生成的报告（运行 06 示例后生成） |
| `a2a_document_*.md` | A2A 文档（运行 A2A 相关示例后生成，文件名含时间戳） |

---

## 4. 关键代码讲解

### 4.1 快速体验三种协议（01_TestConnect.py）

```python
from hello_agents.tools import MCPTool, A2ATool, ANPTool

# 1. MCP: 访问工具（不指定参数，使用内置内存服务器）
mcp_tool = MCPTool()
result = mcp_tool.run({
    "action": "call_tool",
    "tool_name": "add",
    "arguments": {"a": 10, "b": 20}
})
print(f"MCP计算结果: {result}")  # 输出: 30.0

# 2. ANP: 服务发现
anp_tool = ANPTool()
anp_tool.run({
    "action": "register_service",
    "service_id": "calculator",
    "service_type": "math",
    "endpoint": "http://localhost:8080"
})
services = anp_tool.run({"action": "discover_services"})
print(f"发现的服务: {services}")

# 3. A2A: 智能体通信
a2a_tool = A2ATool("http://localhost:5000")
print("A2A工具创建成功")
```

**关键点**:
- `MCPTool()` 不传参数时使用**内存传输（Memory Transport）**，内置演示服务器提供 add/subtract/multiply/divide 等基础工具。
- `A2ATool` 需要指定远程 A2A 服务器的地址，说明 A2A 主要用于网络通信。
- `ANPTool` 的服务注册和发现是**进程内内存操作**，没有持久化能力。

### 4.2 MCPClient 的三种核心操作（02_Connect2MCP.py）

**连接服务器**:
```python
import asyncio
from hello_agents.protocols import MCPClient

client = MCPClient([
    "npx", "-y",
    "@modelcontextprotocol/server-filesystem",
    "."  # 指定根目录
])

async with client:
    tools = await client.list_tools()
    print(f"可用工具: {[t['name'] for t in tools]}")
```

**发现工具**:
```python
async with client:
    tools = await client.list_tools()
    for tool in tools:
        print(f"工具名称: {tool['name']}")
        print(f"描述: {tool.get('description', '无描述')}")
        # 查看参数信息
        if 'inputSchema' in tool:
            schema = tool['inputSchema']
            if 'properties' in schema:
                for param_name, param_info in schema['properties'].items():
                    print(f"  - {param_name} ({param_info.get('type', 'any')}): {param_info.get('description', '')}")
```

**调用工具**:
```python
async with client:
    result = await client.call_tool("read_file", {"path": "my_README.md"})
    print(f"文件内容: \n{result}")
```

**关键点**:
- `MCPClient` 使用 `async with` 确保连接正确关闭。
- `list_tools()` 返回的是 MCP 服务器声明的工具列表，包含 `inputSchema` 描述参数结构。
- `call_tool()` 的第一个参数是工具名，第二个参数是符合 JSON Schema 的参数字典。

### 4.3 MCPTool 的自动展开机制（05_UseMCPToolInAgent.py）

```python
from hello_agents import SimpleAgent, HelloAgentsLLM
from hello_agents.tools import MCPTool

agent = SimpleAgent(name="助手", llm=HelloAgentsLLM())

# 内置演示服务器（自动展开）
mcp_tool = MCPTool()  # 默认 name="mcp"
agent.add_tool(mcp_tool)
# 自动展开为: mcp_add, mcp_subtract, mcp_multiply, mcp_divide, mcp_greet, mcp_get_system_info

# 外部服务器（需指定 name 避免冲突）
fs_tool = MCPTool(
    name="filesystem",  # 唯一名称作为前缀
    description="访问本地文件系统",
    server_command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "."]
)
agent.add_tool(fs_tool)
# 自动展开为: fs_read_file, fs_write_file, fs_list_directory, ...
```

**自动展开的工作原理**:
1. `MCPTool` 连接到服务器，通过 `list_tools()` 发现所有工具。
2. 为每个工具创建包装器，名称格式为 `{name}_{tool_name}`。
3. 注册到 Agent 的 ToolRegistry。
4. Agent 调用时，包装器自动将参数转换为 MCP 格式的 `{"action": "call_tool", "tool_name": "...", "arguments": {...}}`。

**关键点**:
- `name` 参数是 MCP 工具的前缀，使用多个 MCP 服务器时必须指定不同的 `name`。
- 系统自动处理类型转换（如 `"25"` 转为 `25.0`）。
- 自动展开后，Agent 无需手动调用 MCP 协议，像使用普通工具一样使用 MCP 工具。

### 4.4 自定义 MCP 服务器（my_mcp_server.py）

```python
from fastmcp import FastMCP

# 创建 MCP 服务器实例
mcp = FastMCP("MyCustomServer")

# 注册工具
@mcp.tool()
def add(a: float, b: float) -> float:
    """加法计算器"""
    return a + b

# 注册资源
@mcp.resource("config://server")
def get_server_config() -> str:
    """获取服务器配置信息"""
    return json.dumps({"name": "MyCustomServer", "version": "1.0.0"})

# 注册提示模板
@mcp.prompt()
def math_helper() -> str:
    """数学计算助手提示词"""
    return """你是一个数学计算助手。你可以使用以下工具..."""

if __name__ == "__main__":
    mcp.run()  # FastMCP 自动处理 stdio 传输
```

**关键点**:
- 使用 `FastMCP` 库，它是 MCP 协议的 Python 框架封装。
- `@mcp.tool()` 装饰器注册工具，函数名即为工具名。
- `@mcp.resource()` 注册资源，可被客户端读取。
- `@mcp.prompt()` 注册提示模板，辅助 LLM 使用工具。
- 运行 `mcp.run()` 时默认使用 stdio 传输。

### 4.5 MCP 传输方式（04_MCPTransport.py）

```python
from hello_agents.tools import MCPTool

# 1. Memory Transport - 内置演示服务器
mcp_tool = MCPTool()

# 2. Stdio Transport - Python 服务器
mcp_tool = MCPTool(server_command=["python", "my_mcp_server.py"])

# 3. Stdio Transport - npx 社区服务器
mcp_tool = MCPTool(server_command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "."])

# 4. HTTP/SSE/StreamableHTTP - 使用底层 MCPClient
from hello_agents.protocols.mcp.client import MCPClient
client = MCPClient("http://api.example.com/mcp", transport_type="sse")
```

**关键点**:
- `MCPTool` 主要封装 Stdio 和 Memory 传输，对 HTTP/SSE/StreamableHTTP 建议使用底层 `MCPClient`。
- 教程中展示的五种传输模式是 **HelloAgents/FastMCP 框架的封装抽象**，用于简化教学。
- **当前 MCP 官方规范强调 stdio 和 Streamable HTTP 为主要传输方式**，SSE 被视为遗留方式。

### 4.6 A2A 服务器 + 客户端集成（09_A2A_WithAgent.py）

```python
from hello_agents.protocols import A2AServer, A2AClient
from hello_agents import SimpleAgent, HelloAgentsLLM
import threading

# 1. 创建 A2A Agent 服务
tech_expert = A2AServer(
    name="tech_expert",
    description="技术专家，回答技术相关问题",
    version="1.0.0"
)

@tech_expert.skill("answer")
def answer_tech_question(text: str) -> str:
    """回答技术问题"""
    import re
    match = re.search(r'answer\s+(.+)', text, re.IGNORECASE)
    question = match.group(1).strip() if match else text
    return f"技术回答: 关于'{question}'，这是一个技术问题的专业解答..."

# 2. 后台启动 A2A 服务
threading.Thread(target=lambda: tech_expert.run(port=6000), daemon=True).start()

# 3. 封装为 Tool
class A2ATool(Tool):
    def __init__(self, name, description, agent_url, skill_name="answer"):
        self.agent_url = agent_url
        self.skill_name = skill_name
        self.client = A2AClient(agent_url)
        # ...

    def run(self, **kwargs):
        question = kwargs.get('question', '')
        result = self.client.execute_skill(self.skill_name, f"answer {question}")
        return result.get('result', 'No response')

# 4. 添加到 SimpleAgent
receptionist = SimpleAgent(name="接待员", llm=HelloAgentsLLM())
receptionist.add_tool(tech_tool)
receptionist.add_tool(sales_tool)
```

**关键点**:
- A2A 的核心是 `A2AServer` + `A2AClient` 对等通信。
- `@server.skill()` 装饰器注册技能，技能名是 A2A 调用的路由标识。
- 通过 `A2ATool` 封装，A2A 智能体可以像普通工具一样被 `SimpleAgent` 调用。
- 这是 **MCP 与 A2A 的混合使用模式**: MCP 让 Agent 访问工具，A2A 让 Agent 调用其他 Agent。

### 4.7 ANP 服务发现（11_ANPInit.py）

```python
from hello_agents.protocols import ANPDiscovery, register_service, discover_service, ANPNetwork

# 创建服务发现中心
discovery = ANPDiscovery()

# 注册服务
register_service(
    discovery=discovery,
    service_id="nlp_agent_1",
    service_name="NLP处理专家A",
    service_type="nlp",
    capabilities=["text_analysis", "sentiment_analysis", "ner"],
    endpoint="http://localhost:8001",
    metadata={"load": 0.3, "price": 0.01}
)

# 按类型发现服务
nlp_services = discover_service(discovery, service_type="nlp")
print(f"找到 {len(nlp_services)} 个NLP服务")

# 选择负载最低的服务
best_service = min(nlp_services, key=lambda s: s.metadata.get("load", 1.0))
print(f"最佳服务: {best_service.service_name} (负载: {best_service.metadata['load']})")
```

**关键点**:
- `ANPDiscovery` 是**进程内内存对象**，所有服务注册和发现都在同一进程内完成。
- `metadata` 可以携带负载、价格、版本等信息，用于服务选择策略（如负载均衡）。
- 教程的黑体字"ANP 目前只做概念模拟"再次强调这不是生产级实现。

---

## 5. 与前几章的关系

| 章节 | 内容 | 与本章关系 |
|------|------|------------|
| 第六章 | 框架开发实践 | 建立 Tool 抽象和 Agent 核心循环，本章在此基础上引入协议工具 |
| 第七章 | 构建Agent框架 | `SimpleAgent`、`ReActAgent`、`ToolRegistry` 是本章协议的集成载体 |
| 第八章 | 记忆与检索 | 记忆系统为智能体提供内部状态，通信协议让智能体获取外部能力 |
| 第九章 | 上下文工程 | 上下文优化让 Agent 更高效地使用 MCP 工具返回的信息 |
| **第十章** | **智能体通信协议** | **当前章节** |

**演进路径**:

```
单体 Agent（第7章）
  -> 记忆增强（第8章）
  -> 上下文优化（第9章）
  -> 协议互联（第10章）：MCP（连工具）+ A2A（连Agent）+ ANP（连网络）
```

---

## 6. 本项目实现差异

### 6.1 版本差异

| 项目 | 教程要求 | 本项目 |
|------|----------|--------|
| hello-agents | 0.2.2 | 0.2.2（2026-08-25 实测） |
| 协议依赖 | 随 protocol extra 安装 | fastmcp 2.12.5 / mcp 1.16.0 / authlib 1.7.2 |
| 安装方式 | `pip install "hello-agents[protocol]==0.2.2"` | 当前环境已安装，本章不重复安装 |
| Node.js | 需要 | 需要（npx 运行社区 MCP 服务器） |

**重要提醒**:
- 本章当前环境与教程均为 `hello-agents 0.2.2`。Chapter 9 使用过的 `0.2.8` 是历史环境记录，不代表本章实际版本。
- **不要主动升级或降级**。如果遇到不兼容，先通过 `pip show hello-agents` 核对当前解释器中的真实版本，再查阅对应版本的 API 签名。
- 如果 `hello_agents.protocols` 模块缺失，可能需补装 `pip install "hello-agents[protocol]"`。

### 6.2 模型配置

本项目沿用前几章的 Kimi 模型配置：

```python
# 本项目写法（已在 .env 中配置）
llm = HelloAgentsLLM()  # 自动读取环境变量

# 等效于
llm = HelloAgentsLLM(
    model=os.getenv("OPENAI_MODEL"),          # kimi-k2.6
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),    # https://kimi.a7m.com.cn/v1
)
```

### 6.3 关键环境约定

**`load_dotenv` 必须在 `hello_agents` 导入之前调用**:

```python
from dotenv import load_dotenv
load_dotenv()  # 必须在所有 hello_agents 导入之前

from hello_agents import SimpleAgent, HelloAgentsLLM
from hello_agents.tools import MCPTool
```

部分 `hello_agents` 模块在导入时就会创建或缓存配置对象（如 `HelloAgentsLLM` 的默认参数），这些配置对象在初始化时读取环境变量。如果 `load_dotenv()` 在导入之后才被调用，已缓存的配置对象不会重新读取环境变量。这不是 `os.getenv` 本身的问题（`os.getenv` 每次调用都读取当前进程的环境变量表），而是模块级缓存导致的问题。

**UTF-8 控制台输出**:

如果控制台输出出现乱码，在运行前设置 PowerShell 环境变量：

```powershell
$env:PYTHONIOENCODING="utf-8"
```

也可以将这一行加到 `$PROFILE` 中持久生效。

**`OPENAI_*` 环境变量命名**:

本项目使用 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` 的命名约定（兼容 OpenAI 客户端 SDK 的自动检测）。`hello_agents` 框架的 `HelloAgentsLLM()` 默认读取这些变量。`code/.env.example` 也使用同一套命名，可直接参考。（注意：`LLM_TIMEOUT` 是独立超时控制变量，不属于 `OPENAI_*` 系列。）

### 6.4 可选依赖说明

| 依赖 | 用途 | 是否必需 |
|------|------|----------|
| Node.js + npx | 运行社区 MCP 服务器（如 `server-filesystem`、`server-github`） | 可选（MCP Stdio 传输时可能需要） |
| GitHub Personal Access Token | 访问 GitHub MCP 服务器 | 可选（仅 `03_GitHubMCP.py` 需要） |
| `a2a-sdk` | A2A 协议底层实现 | 可选（`pip install a2a-sdk`） |
| `fastmcp` | MCP 服务器框架 | 需要（通常随 `hello-agents[protocol]` 安装） |

**不会自动安装缺失依赖**。遇到 `ModuleNotFoundError` 时会看到缺失包名和对应的安装命令（如 `pip install a2a-sdk`），但只有在明确授权后才会执行安装。

### 6.5 代码安全性说明

本章代码来源于固定版本（`45dd84e6`）的 `hello-agents` 教程仓库。为保留教学可追溯性，代码中保留了部分教学捷径，例如直接使用 `eval()` 执行字符串、使用过于宽泛的 `except:` 捕获所有异常等。这些做法在开发调试环境中便于演示概念，但**不能直接用于生产环境**。若需要投入生产，应当重写相关部分，改用受限的解析方式、显式捕获具体异常类型、增加输入校验和错误日志。

---

## 7. 运行方式

### 7.1 环境检查

```powershell
# 激活环境
conda activate agent_study

# 检查 hello-agents 版本
pip show hello-agents

# 检查协议相关模块是否可用
python -c "from hello_agents.protocols import MCPClient; print('MCPClient OK')"
python -c "from hello_agents.tools import MCPTool; print('MCPTool OK')"

# 检查 Node.js/npx 是否可用（如需运行社区 MCP 服务器）
npx --version
```

### 7.2 运行 MCP 示例

```powershell
# 进入章节目录
cd chapter10

# 01 - 快速体验三种协议（不需要外部服务器）
python code/01_TestConnect.py

# 02 - MCPClient 连接服务器（需要 npx, 首次运行会下载 server-filesystem）
python code/02_Connect2MCP.py

# 03 - GitHub MCP（可选；Token 放在根目录 .env 或当前会话，禁止写入源码）
$env:GITHUB_PERSONAL_ACCESS_TOKEN="your_token_here"
python code/03_GitHubMCP.py

# 04 - 传输方式演示
python code/04_MCPTransport.py

# 05 - 在 Agent 中使用 MCP 工具
python code/05_UseMCPToolInAgent.py

# 14 - 天气 MCP 服务器测试
python code/14_test_weather_server.py
python code/14_weather_agent.py
```

**已验证结果（2026-08-25）**: `03_GitHubMCP.py` 成功发现 26 个 GitHub 工具，并返回有效的仓库搜索结果。程序退出时曾出现 `unclosed transport` / `Event loop is closed` 清理告警，但业务调用已经完成，且检查时没有残留 `server-github` Node 进程，因此该次运行中它属于非致命的 asyncio 子进程回收告警，不应误判为 MCP 调用失败。若后续出现进程残留或结果不完整，再单独排查客户端关闭时序。

### 7.3 运行 A2A 示例

```powershell
# 07 - 简单 A2A 计算器 Agent
python code/07_SimpleA2AAgent.py

# 09 - A2A + SimpleAgent 集成
python code/09_A2A_WithAgent.py

# 10 - Agent 协商
python code/10_AgentNegotiation.py
```

### 7.4 运行 ANP 示例

```powershell
# 11 - ANP 服务发现与注册
python code/11_ANPInit.py

# 12 - ANP 任务分发
python code/12_ANPTaskDistribution.py

# 13 - ANP 负载均衡
python code/13_ANPLoadBalancing.py
```

### 7.5 环境变量配置

项目根目录的 `.env` 文件已在前面章节的配置过程中创建并设置好。`code/.env.example` 是本章代码的参考模板，**仅用于对照说明**，无需复制或覆盖已有的根目录 `.env`。

`code/.env.example` 中使用的变量名：

```ini
# 必须配置（与根目录 .env 一致）
OPENAI_MODEL=your-model-name
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=your-api-base-url

# 超时（可选，默认 60 秒）
LLM_TIMEOUT=60

# 可选（GitHub MCP 需要）
GITHUB_PERSONAL_ACCESS_TOKEN=your_github_token
```

---

## 8. 文件学习路径

建议按以下顺序阅读代码文件，遵循"MCP 先 -> A2A 中间 -> ANP 最后"的递进逻辑。

### 第一阶段：MCP 协议（01-06, 14, my_mcp_server）

| 步骤 | 文件 | 学习重点 |
|------|------|----------|
| 1 | `01_TestConnect.py` | 三种协议的基本调用方式，感受 API 差异 |
| 2 | `02_Connect2MCP.py` | `MCPClient` 的连接、发现、调用流程，`async with` 用法 |
| 3 | `04_MCPTransport.py` | 五种传输方式，理解 Memory vs Stdio vs HTTP/SSE 的区别 |
| 4 | `my_mcp_server.py` | 如何用 `FastMCP` 编写自己的 MCP 服务器，`@mcp.tool` / `@mcp.resource` / `@mcp.prompt` |
| 5 | `05_UseMCPToolInAgent.py` | MCPTool 的自动展开机制，`name` 前缀的作用 |
| 6 | `06_MultiAgentDocumentAssist.py` | 多 Agent 编排 + MCP 工具组合的完整案例 |
| 7 | `14_weather_mcp_server.py` | 带真实 HTTP 请求的 MCP 服务器（wttr.in 天气 API） |
| 8 | `14_weather_agent.py` | 在 Agent 中展开使用天气 MCP 工具 |
| 9 | `14_test_weather_server.py` | 用 `MCPClient` 直接测试 MCP 服务器 |

### 第二阶段：A2A 协议（07-10）

| 步骤 | 文件 | 学习重点 |
|------|------|----------|
| 10 | `07_SimpleA2AAgent.py` | `A2AServer` 的基本用法，`@server.skill` 注册技能 |
| 11 | `08_CustomA2AAgent.py` | 自定义技能和技能路由 |
| 12 | `09_A2A_Server.py` | A2A 服务端实现 |
| 13 | `09_A2A_Client.py` | A2A 客户端调用 |
| 14 | `09_A2A_Network.py` | A2A 网络通信 |
| 15 | `09_A2A_WithAgent.py` | **核心文件**: A2A Server + Thread + Tool 封装 + SimpleAgent 集成 |
| 16 | `10_AgentNegotiation.py` | A2A 的协商机制（propose/counter-proposal） |
| 17 | `10_CustomerService.py` | A2A 客服机器人实战案例 |

### 第三阶段：ANP 协议（11-13）

| 步骤 | 文件 | 学习重点 |
|------|------|----------|
| 18 | `11_ANPInit.py` | `ANPDiscovery`、`register_service`、`discover_service`、`ANPNetwork` |
| 19 | `12_ANPTaskDistribution.py` | 基于服务发现的任务分发 |
| 20 | `13_ANPLoadBalancing.py` | 基于 `metadata.load` 的负载均衡策略 |

---

## 9. 安全注意事项

### 9.1 MCP 文件系统服务器

```python
# 危险: 暴露整个文件系统
MCPTool(server_command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "/"])

# 安全: 只暴露当前工作目录
MCPTool(server_command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "."])
```

- `server-filesystem` 的根目录参数决定了 Agent 能访问的文件范围。
- 永远不要使用 `/`（Windows 下为 `C:\`）作为根目录，除非你完全信任 Agent 的决策。
- 建议使用项目子目录作为根目录。

### 9.2 API Token 和安全

- `.env` 文件中的 API Key 和 GitHub Token 不应提交到版本控制。
- GitHub MCP 服务器需要 `GITHUB_PERSONAL_ACCESS_TOKEN` 环境变量，确保只授予最小权限（read-only 优先）。
- 远程 MCP 服务器（Streamable HTTP）应使用 HTTPS 和认证机制。

### 9.3 远程服务器风险

风险类型因服务器部署方式而异：

- **通过 npx 或 Python 运行的本地 MCP 包**：这些包作为子进程在本地执行，可以访问宿主机的文件系统、网络、环境变量等资源。如果包本身包含恶意代码，它可以直接对本地系统造成损害，而不仅限于 MCP 协议暴露的工具。
- **远程 MCP 服务器（Streamable HTTP/SSE）**：风险在于远程服务器可能在其暴露的 Tools/Resources/Prompts 中植入误导性内容，或在获得的权限范围内执行不当操作。远程服务器本身不直接访问你的本地环境。

**如何降低风险**：
- 验证包维护者身份和版本号，而不是仅凭包名前缀（如 `@modelcontextprotocol/server-*`）决定信任。npm 和 PyPI 上都可能出现名称相似的仿冒包。
- 使用 `MCPClient` 的 `async with` 确保连接及时关闭。
- 对远程服务器，限制其可访问的资源和工具范围，并确保使用 HTTPS 加密传输。

### 9.4 工具副作用

- MCP 工具可以执行写入、删除等破坏性操作（如 `write_file`、`delete_file`）。
- 在 Agent 中启用 MCP 工具前，评估工具可能带来的副作用。
- 生产环境中应实现工具调用的审核和批准机制。

---

## 10. 学习建议

### 10.1 重点理解

1. **三种协议的设计哲学差异**: MCP（工具标准化）vs A2A（Agent 对等通信）vs ANP（服务发现网络）。
2. **MCP 的 Host/Client/Server 三层架构**: 每层的职责分离是 MCP 可扩展性的基础。
3. **MCPTool 自动展开机制**: 理解它如何将 MCP 服务器工具无缝集成到 Agent 的 Tool 系统中。
4. **A2A 的 Task/Artifact 抽象**: 基于任务的协作模式与 MCP 基于工具的调用模式的本质区别。
5. **ANP 的概念性定位**: 它是教学演示，不是生产协议，理解其核心思想即可。

### 10.2 实验建议

1. **修改 my_mcp_server.py**: 添加新的工具（如 `get_time`、`random_number`），测试自动展开。
2. **连接多个 MCP 服务器**: 同时使用文件系统 + 数学计算 + 自定义服务器，观察 Agent 如何选择工具。
3. **修改 A2A 协商逻辑**: 在 `10_AgentNegotiation.py` 中修改协商标准，观察 Agent 如何调整策略。
4. **对比不同传输方式**: 运行 `04_MCPTransport.py` 中的 Memory 和 Stdio 方式，理解性能差异。
5. **扩展天气服务器**: 为 `14_weather_mcp_server.py` 添加更多城市和天气预报功能。

### 10.3 常见问题

**Q: MCP 和 Function Calling 是什么关系？**
A: Function Calling 是 LLM 的**核心能力**（模型理解何时调用函数），MCP 是**基础设施协议**（标准化工具如何被描述和调用）。两者相辅相成，不是竞争关系。

**Q: 教程中的五种传输方式是什么？**
A: 五种传输方式（Memory、Stdio、HTTP、SSE、StreamableHTTP）是 **HelloAgents/FastMCP 框架的封装抽象**，用于简化教学。当前 MCP 官方规范主要推荐 stdio 和 Streamable HTTP，SSE 已标记为遗留方式。

**Q: 为什么 A2A 代码需要 `threading`？**
A: A2A 基于 HTTP 服务，需要后台线程运行 `A2AServer.run()` 来监听请求，主线程才能执行客户端逻辑。这是教学演示的简化方式，生产环境应使用真正的进程管理。

**Q: ANP 的代码能用在生产环境吗？**
A: **不能**。本章的 ANP 实现是概念性的轻量级实现，所有服务注册和发现都在进程内内存中完成，没有网络通信、持久化、容错机制。生产环境可参考 [AgentConnect](https://github.com/agent-network-protocol/AgentConnect)。

**Q: 为什么本章的代码有的需要 npx，有的需要 a2a-sdk？**
A: MCP 社区服务器（如 `server-filesystem`）通过 npx 分发，无需手动安装。A2A 协议依赖 `a2a-sdk` 包，需要 `pip install a2a-sdk`。ANP 协议完全在 hello-agents 框架内实现，无需额外依赖。

**Q: 为什么我的 `HelloAgentsLLM()` 读取不到环境变量？**
A: 确保 `load_dotenv()` 在 `from hello_agents import ...` 之前调用。部分 `hello_agents` 模块在导入时就会创建或缓存配置对象，这些对象在初始化时读取环境变量。如果 `load_dotenv()` 在导入之后才被调用，已缓存的配置对象不会自动刷新。这不是 `os.getenv` 本身的问题（`os.getenv` 每次调用都读取当前进程的环境变量表），而是模块级缓存导致的问题。

---

## 11. 参考来源

- **教程文档**: [Hello-Agents 第十章](https://github.com/datawhalechina/hello-agents/blob/main/docs/chapter10/%E7%AC%AC%E5%8D%81%E7%AB%A0%20%E6%99%BA%E8%83%BD%E4%BD%93%E9%80%9A%E4%BF%A1%E5%8D%8F%E8%AE%AE.md)
- **官方代码**: `code/chapter10/` 目录（commit `45dd84e626a91997294ac8d4d44f18b29a411c6e`）
- **MCP 规范**: [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/latest/)
- **Awesome MCP Servers**: https://github.com/punkpeye/awesome-mcp-servers
- **MCP Servers 目录**: https://mcpservers.org/
- **官方 MCP Servers**: https://github.com/modelcontextprotocol/servers
- **A2A 官方**: Google Agent-to-Agent Protocol
- **ANP 仓库**: https://github.com/agent-network-protocol/AgentConnect

---

**下一步**: 阅读 `chapter10/code/` 目录下的代码文件，按照第 8 节的建议顺序逐步学习。先从 `01_TestConnect.py` 开始，感受三种协议的基本调用方式，然后深入学习 MCP。
