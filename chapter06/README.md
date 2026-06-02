# 第六章 框架开发实践

> 学习主流 Agent 框架：AutoGen、AgentScope、CAMEL、LangGraph

---

## 📚 本章概览

本章是**工程师核心技能**，学习如何使用业界主流的 Agent 框架构建复杂的多智能体应用。

### 为什么需要框架？

- ✅ **提升开发效率** - 封装通用逻辑，避免重复造轮子
- ✅ **组件解耦** - 模型层、工具层、记忆层分离
- ✅ **标准化** - 统一的状态管理、日志记录、调试机制
- ✅ **可观测性** - 内置事件回调，追踪 Agent 运行轨迹

---

## 🎯 四大框架对比


| 框架             | 核心理念   | 架构特点                     | 适用场景      |
| -------------- | ------ | ------------------------ | --------- |
| **AutoGen**    | 对话驱动协作 | 多智能体群聊、角色分工              | 协作任务、软件开发 |
| **AgentScope** | 消息驱动架构 | 异步、分布式、高并发               | 大规模、企业级应用 |
| **CAMEL**      | 角色扮演   | 自主协作、Inception Prompting | 复杂创作任务    |
| **LangGraph**  | 图结构工作流 | 状态机、循环、分支                | 复杂流程控制    |


---

## 📝 代码实现

### 1. AutoGen - 比特币价格显示应用

**文件**: `code/01_autogen_bitcoin.py`

**核心概念**:

- `AssistantAgent` - AI 助理智能体（思考）
- `UserProxyAgent` - 用户代理（执行 + 人类在环）
- `RoundRobinGroupChat` - 轮询群聊（顺序协作）
- `TextMentionTermination` - 文本触发终止

**智能体团队**:

1. **ProductManager** - 产品经理，需求分析与规划
2. **Engineer** - 工程师，代码实现
3. **CodeReviewer** - 代码审查员，质量把控
4. **UserProxy** - 用户代理，任务发起与验收

**关键代码**:

```python
team_chat = RoundRobinGroupChat(
    participants=[product_manager, engineer, code_reviewer, user_proxy],
    termination_condition=TextMentionTermination("TERMINATE"),
    max_turns=20,
)
```

---

### 2. AgentScope - 三国狼人杀游戏

**文件**: `code/02_agentscope_werewolf.py`

**核心概念**:

- `Msg` - 消息是交互的基本单元
- `MsgHub` - 消息中心，路由与分发
- `DialogAgent` - 对话智能体基类
- `fanout_pipeline` - 并行管道，同时收集多个响应

**架构特点**:

- **消息驱动** - 所有交互抽象为消息的发送和接收
- **异步解耦** - 天然支持高并发
- **位置透明** - 智能体可在本地或远程，消息系统自动路由
- **容错处理** - 异常智能体不影响整体流程

**游戏设计**:

- 6名玩家，每人有两个身份：游戏角色 + 三国人物
- 狼人（孙权、周瑜）vs 好人（曹操、张飞、司马懿、赵云）
- 结构化输出约束游戏规则

---

### 3. CAMEL - AI科普电子书创作

**文件**: `code/03_camel_ebook.py`

**核心概念**:

- `RolePlaying` - 角色扮演场景
- `AI User` - 任务提出者（AI心理学家）
- `AI Assistant` - 任务执行者（AI作者）
- `Inception Prompting` - 引导性提示，确保高效协作

**设计原理**:

1. **角色互补** - 两个智能体拥有互补的专业能力
2. **引导性提示** - 系统消息中定义角色、目标、行为约束
3. **结构化协作** - 一次只提一个步骤，完成后用 `<SOLUTION>` 标记

**关键代码**:

```python
role_playing = RolePlaying(
    assistant_role_name="AI作者",
    user_role_name="AI心理学家",
    task_prompt="创作一本拖延症科普电子书...",
)
```

---

### 4. LangGraph - 三步智能搜索问答助手

**文件**: `code/04_langgraph_search_assistant.py`

**核心概念**:

- **图结构** - 将 Agent 流程建模为图（节点 + 边）
- **状态机** - 每个节点有明确的状态和转换条件
- **循环支持** - 天然支持 Reflection 等迭代流程
- **可视化** - 可以直观展示复杂工作流

**设计特点**:

```
节点(Node): 调用LLM、执行工具、条件判断
边(Edge): 定义节点间的跳转逻辑
循环(Cycles): 支持迭代、修正、自我反思
```

**三步流程**:

1. **Understand** - 理解用户查询，生成适合搜索的关键词
2. **Search** - 调用 Tavily API 进行真实搜索
3. **Answer** - 基于搜索结果生成最终回答，搜索失败时回退到模型自身知识

**关键代码**:

```python
workflow = StateGraph(SearchState)
workflow.add_node("understand", understand_query_node)
workflow.add_node("search", tavily_search_node)
workflow.add_node("answer", generate_answer_node)

workflow.add_edge(START, "understand")
workflow.add_edge("understand", "search")
workflow.add_edge("search", "answer")
workflow.add_edge("answer", END)
```

**代码对齐说明**:

- 已按 Hello-Agents 第六章 6.5.2「三步问答助手」代码片段组合实现。
- 教程使用 `LLM_MODEL_ID` / `LLM_API_KEY` / `LLM_BASE_URL`，本项目按记忆规则改为 `.env` 中的 `OPENAI_MODEL` / `OPENAI_API_KEY` / `OPENAI_BASE_URL`。
- 教程搜索结果格式化部分以省略号展示，本项目补齐了 Tavily 返回结果的格式化逻辑。

---

## 🔍 框架选择指南

```
任务类型分析:
├── 多智能体协作对话？
│   └── 是 → AutoGen（对话驱动）
├── 需要高并发/分布式？
│   └── 是 → AgentScope（消息驱动）
├── 自主角色扮演任务？
│   └── 是 → CAMEL（Inception Prompting）
├── 复杂流程控制/循环？
│   └── 是 → LangGraph（图结构）
└── 企业级/生产环境？
    └── 推荐 AgentScope（工程化）
```

---

## 💡 核心启示

### 0. 本章学习总结

- **AutoGen** 适合把任务组织成多角色对话协作，核心是角色职责、发言顺序和终止条件。
- **AgentScope** 更偏工程化与消息驱动，适合多智能体并发、分布式和容错场景。
- **CAMEL** 通过 RolePlaying 和 Inception Prompting 降低双智能体自主协作的设计成本。
- **LangGraph** 把智能体流程显式建模为状态机和有向图，适合需要可控步骤、状态追踪、分支和循环的工作流。
- 四类框架的关键取舍是：对话式框架更强调“角色协作涌现”，LangGraph 更强调“流程显式控制”，AgentScope 更强调“生产级工程能力”。

### 1. 架构演进路径

```
手动实现 (Chapter 4)
    ↓
低代码平台 (Chapter 5) - 快速验证
    ↓
框架开发 (Chapter 6) - 生产环境
    ↓
自建框架 (Chapter 7) - 深度定制
```

### 2. 工程师成长路径


| 阶段     | 能力   | 工具                    |
| ------ | ---- | --------------------- |
| **初级** | 使用框架 | AutoGen、Dify          |
| **中级** | 理解架构 | 阅读源码、设计模式             |
| **高级** | 自建框架 | Chapter 7、HelloAgents |


### 3. 关键技能

**必须掌握**:

1. ✅ 异步编程 (`async/await`)
2. ✅ 消息驱动架构
3. ✅ 结构化输出 (Pydantic)
4. ✅ 角色设计 (Prompt Engineering)
5. ✅ 状态管理

**进阶技能**:

- 分布式系统设计
- 容错与恢复机制
- 可观测性（日志、追踪、监控）

---

## 📖 学习建议

1. **先运行示例** - 每个框架至少运行一个完整案例
2. **修改参数** - 调整智能体提示词，观察行为变化
3. **对比实现** - 用不同框架实现同一任务，对比优劣
4. **阅读源码** - 理解框架的底层设计
5. **实际项目** - 在真实项目中应用

---

## 🚀 下一步

**Chapter 7: 构建你的 Agent 框架**

从零开始构建自己的 Agent 框架，深入理解：

- 核心抽象层设计
- 模型接口统一
- 工具注册与执行
- 记忆系统实现
- 多智能体通信

---

**参考链接**:

- [AutoGen GitHub](https://github.com/microsoft/autogen)
- [AgentScope GitHub](https://github.com/modelscope/agentscope)
- [CAMEL GitHub](https://github.com/camel-ai/camel)
- [LangGraph 文档](https://python.langchain.com/docs/langgraph)
