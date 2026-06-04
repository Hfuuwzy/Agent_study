# 第八章 记忆与检索

> [!info] 学习概览
> **目标**: 为 HelloAgents 框架增加记忆系统和 RAG 能力
> **实践**: 实现四种记忆类型和检索增强生成系统
> **重点**: 理解记忆系统架构、RAG 技术原理与实现

---

## 1. 本章定位

本章在第七章构建的 Agent 框架基础上，增加两个核心能力：

1. **记忆系统 (Memory System)** - 让智能体能够记住历史交互和学习经验
2. **检索增强生成 (RAG)** - 让智能体能够利用外部知识库回答问题

这两个能力是构建真正智能、可用的 Agent 系统的关键。

---

## 2. 核心概念

### 2.1 人类记忆系统的启发

人类记忆是一个多层级系统，智能体的记忆设计借鉴了认知心理学的研究成果：

| 记忆类型 | 特点 | 对应智能体实现 |
|---------|------|--------------|
| **感觉记忆** | 0.5-3秒，容量巨大 | （框架内部处理） |
| **工作记忆** | 15-30秒，7±2个项目 | `WorkingMemory` - 临时对话上下文 |
| **情景记忆** | 个人经历和事件 | `EpisodicMemory` - 交互事件历史 |
| **语义记忆** | 一般知识和概念 | `SemanticMemory` - 知识图谱存储 |
| **感知记忆** | 图像、音频等多模态 | `PerceptualMemory` - 多媒体信息 |

### 2.2 LLM 的局限性

**局限一：无状态导致的对话遗忘**

```python
# 第七章的 Agent 使用方式
agent = SimpleAgent(name="学习助手", llm=HelloAgentsLLM())

# 第一次对话
response1 = agent.run("我叫张三，正在学习Python")
# 输出: "很好！Python基础语法是编程的重要基础..."

# 第二次对话（新的会话）
response2 = agent.run("你还记得我的学习进度吗？")
# 输出: "抱歉，我不知道您的学习进度..."
```

**局限二：模型内置知识的局限性**

- 知识时效性：训练数据有时间截止点
- 专业领域知识不足
- 可能出现幻觉（生成错误信息）
- 无法提供信息来源

### 2.3 RAG 技术

**什么是 RAG？**

检索增强生成（Retrieval-Augmented Generation）结合了信息检索和文本生成：

1. **检索 (Retrieval)** - 从知识库查询相关内容
2. **增强 (Augmentation)** - 将检索结果融入提示词
3. **生成 (Generation)** - 基于上下文生成准确答案

**RAG 工作流程：**

```
用户提问 → 向量化查询 → 检索相关知识 → 构建增强提示 → LLM生成答案
    ↑                                                      ↓
    └────── 知识库（文档向量化存储）←──── 文档预处理 ←──────┘
```

---

## 3. 架构设计

### 3.1 记忆系统架构

```
HelloAgents 记忆系统
├── 基础设施层
│   ├── MemoryManager - 记忆管理器（统一调度）
│   ├── MemoryItem - 记忆数据结构
│   ├── MemoryConfig - 配置管理
│   └── BaseMemory - 记忆基类
├── 记忆类型层
│   ├── WorkingMemory - 工作记忆（临时信息）
│   ├── EpisodicMemory - 情景记忆（事件序列）
│   ├── SemanticMemory - 语义记忆（知识图谱）
│   └── PerceptualMemory - 感知记忆（多模态）
├── 存储后端层
│   ├── QdrantVectorStore - 向量存储
│   ├── Neo4jGraphStore - 图存储
│   └── SQLiteDocumentStore - 文档存储
└── 嵌入服务层
    ├── DashScopeEmbedding - 通义千问嵌入
    ├── LocalTransformerEmbedding - 本地嵌入
    └── TFIDFEmbedding - TFIDF嵌入
```

### 3.2 RAG 系统架构

```
HelloAgents RAG系统
├── 文档处理层
│   ├── DocumentProcessor - 文档解析
│   ├── Document - 文档对象
│   └── Pipeline - RAG管道
├── 嵌入表示层
│   └── 复用记忆系统的嵌入服务
├── 向量存储层
│   └── QdrantVectorStore - 向量数据库
└── 智能问答层
    ├── 多策略检索（向量 + MQE + HyDE）
    ├── 上下文构建
    └── LLM增强生成
```

---

## 4. 核心组件详解

### 4.1 MemoryTool - 记忆工具接口

`MemoryTool` 是 Agent 与记忆系统交互的统一接口：

```python
from hello_agents.tools import MemoryTool

# 创建记忆工具
memory_tool = MemoryTool(user_id="user123")

# 添加记忆
memory_tool.execute("add",
    content="张三是一名Python开发者",
    memory_type="semantic",
    importance=0.8
)

# 搜索记忆
memory_tool.execute("search", query="Python开发者", limit=5)

# 遗忘记忆
memory_tool.execute("forget", strategy="importance_based", threshold=0.2)

# 整合记忆（短期→长期）
memory_tool.execute("consolidate",
    from_type="working",
    to_type="episodic",
    importance_threshold=0.7
)
```

**支持的操作：**

| 操作 | 说明 | 示例 |
|-----|------|------|
| `add` | 添加记忆 | 存储用户信息、对话内容 |
| `search` | 搜索记忆 | 检索相关历史信息 |
| `summary` | 记忆摘要 | 获取用户画像 |
| `forget` | 遗忘记忆 | 清理不重要/过时信息 |
| `consolidate` | 整合记忆 | 工作记忆→情景记忆 |

### 4.2 四种记忆类型

#### (1) 工作记忆 (WorkingMemory)

**特点：**
- 容量有限（默认50条）
- TTL自动清理
- 纯内存存储，访问极快
- 混合检索：TF-IDF + 关键词匹配

**评分公式：**
```
final_score = (vector_score × 0.7 + keyword_score × 0.3) × time_decay × importance_weight
importance_weight = 0.8 + (importance × 0.4)
```

#### (2) 情景记忆 (EpisodicMemory)

**特点：**
- SQLite + Qdrant 混合存储
- 支持时间序列检索
- 结构化过滤 + 语义检索

**评分公式：**
```
score = (vector_similarity × 0.8 + recency × 0.2) × importance_weight
importance_weight = 0.8 + (importance × 0.4)
```

#### (3) 语义记忆 (SemanticMemory)

**特点：**
- Neo4j + Qdrant 混合架构
- 知识图谱存储实体和关系
- 混合检索：向量 + 图 + 语义推理

**评分公式：**
```
score = (vector_score × 0.7 + graph_score × 0.3) × importance_weight
importance_weight = 0.8 + (importance × 0.4)
```

#### (4) 感知记忆 (PerceptualMemory)

**特点：**
- 支持多模态数据（文本、图像、音频）
- 跨模态相似性搜索
- 模态分离的向量存储

**评分公式：**
```
score = (vector_similarity × 0.8 + recency × 0.2) × importance_weight
```

### 4.3 RAGTool - 检索增强工具

`RAGTool` 为 Agent 提供知识检索能力：

```python
from hello_agents.tools import RAGTool

# 创建 RAG 工具
rag_tool = RAGTool(knowledge_base_path="./knowledge_base")

# 检索知识
result = rag_tool.execute("search",
    query="Python装饰器是什么",
    top_k=3,
    use_mqe=True,  # 多查询扩展
    use_hyde=True  # 假设性文档嵌入
)

# 添加文档到知识库
rag_tool.execute("add_documents", file_paths=["./docs/python_guide.pdf"])
```

**核心功能：**

| 功能 | 说明 |
|-----|------|
| 向量检索 | 基于语义相似度检索 |
| MQE | 多查询扩展，提高召回率 |
| HyDE | 假设性文档嵌入，提高准确性 |
| 上下文构建 | 智能片段合并与截断 |

---

## 5. 快速体验

### 5.1 环境配置

**安装 HelloAgents：**

```bash
# 安装框架（包含所有依赖）
pip install "hello-agents[all]==0.2.0"

# 下载 spaCy 模型
python -m spacy download zh_core_web_sm
python -m spacy download en_core_web_sm
```

**配置环境变量 (.env)：**

```bash
# 大模型配置
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://kimi.a7m.com.cn/v1
OPENAI_MODEL=kimi-k2.6

# Qdrant 向量数据库
QDRANT_URL=https://your-cluster.qdrant.tech:6333
QDRANT_API_KEY=your_key

# Neo4j 图数据库
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

# Embedding 配置
EMBED_MODEL_TYPE=dashscope
EMBED_API_KEY=your_dashscope_key
```

### 5.2 30秒上手

```python
from hello_agents import SimpleAgent, HelloAgentsLLM, ToolRegistry
from hello_agents.tools import MemoryTool, RAGTool

# 创建 Agent
llm = HelloAgentsLLM()
agent = SimpleAgent(name="智能助手", llm=llm)

# 创建工具注册表
tool_registry = ToolRegistry()

# 添加记忆工具
memory_tool = MemoryTool(user_id="user123")
tool_registry.register_tool(memory_tool)

# 添加 RAG 工具
rag_tool = RAGTool(knowledge_base_path="./knowledge_base")
tool_registry.register_tool(rag_tool)

# 配置工具
agent.tool_registry = tool_registry

# 开始对话
response = agent.run("你好！请记住我叫张三")
print(response)
```

---

## 6. 学习建议

### 6.1 重点理解

1. **记忆系统的分层设计**：理解四种记忆类型的区别和应用场景
2. **评分算法的意义**：为什么使用不同的权重组合？
3. **RAG 的核心价值**：解决什么问题？如何提升回答质量？
4. **混合存储的优势**：为什么同时使用向量数据库和图数据库？

### 6.2 实验建议

1. **修改重要性权重**：观察不同参数对检索结果的影响
2. **对比不同记忆类型**：测试工作记忆和情景记忆的 TTL 差异
3. **RAG 效果对比**：对比使用/不使用 RAG 的回答质量
4. **多模态实验**：上传图片/音频，测试感知记忆功能

### 6.3 常见问题

**Q: 为什么需要四种记忆类型？**
A: 不同信息有不同生命周期和使用场景。临时对话用工作记忆，历史事件用情景记忆，通用知识用语义记忆，多媒体用感知记忆。

**Q: TTL 机制如何工作？**
A: WorkingMemory 默认60分钟过期，会自动清理；其他记忆类型持久化存储。

**Q: RAG 和记忆系统有什么区别？**
A: 记忆系统存储智能体与用户的交互历史，RAG 从外部知识库检索信息。两者互补。

---

## 7. 参考来源

- **教程文档**: [Hello-Agents 第八章](https://github.com/datawhalechina/hello-agents/blob/main/docs/chapter8/%E7%AC%AC%E5%85%AB%E7%AB%A0%20%E8%AE%B0%E5%BF%86%E4%B8%8E%E6%A3%80%E7%B4%A2.md)
- **框架源码**: `hello_agents.memory` 模块
- **论文参考**: 
  - [1] 认知心理学记忆模型
  - RAG Survey Papers

---

**下一步**: 阅读 `code/` 目录下的示例代码，动手实验记忆和 RAG 功能。
