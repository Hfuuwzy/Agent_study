# 第九章 上下文工程

> [!info] 学习概览
> **目标**: 理解上下文工程的核心概念，掌握 ContextBuilder、NoteTool、TerminalTool 的使用
> **实践**: 构建一个长时程代码助手，演示上下文工程的实际应用
> **重点**: 理解 GSSC 流水线、结构化笔记、即时上下文检索

---

## 1. 本章定位

本章在第八章记忆与检索的基础上，引入**上下文工程（Context Engineering）**的方法论。记忆系统解决了"记住什么"的问题，而上下文工程解决"如何高效利用有限上下文窗口"的问题。

**核心问题**：如何在每次模型调用前，以可复用、可度量、可演进的方式，拼装并优化输入上下文？

**本章新增组件**：
1. **ContextBuilder** - 上下文构建器，实现 GSSC 流水线
2. **NoteTool** - 结构化笔记工具，支持持久化记忆管理
3. **TerminalTool** - 终端工具，支持文件系统操作和即时上下文检索

---

## 2. 核心概念

### 2.1 上下文工程 vs. 提示工程

| 维度 | 提示工程 | 上下文工程 |
|------|----------|------------|
| **关注点** | 如何编写有效的提示词 | 如何策划与维护最优的信息集合 |
| **范围** | 系统提示、用户输入 | 包含工具、MCP、外部数据、消息历史等所有信息 |
| **时间维度** | 单轮优化 | 跨多轮推理的状态管理 |
| **核心挑战** | 词句选择 | 有限窗口内的信息筛选 |

### 2.2 上下文腐蚀（Context Rot）

LLM 和人类一样，在信息过多时会"走神"。随着上下文窗口中的 tokens 增加，模型从上下文中准确回忆信息的能力反而下降。

**关键洞察**：
- 上下文是**有限资源**，具有边际收益递减
- Transformer 的注意力机制是 O(n²) 复杂度
- 模型对长序列的建模能力会被"拉薄"

### 2.3 有效上下文的"解剖学"

**系统提示（System Prompt）**：
- 语言清晰、直白，信息层级"刚刚好"
- 避免过度硬编码或过于空泛
- 用 XML/Markdown 分隔不同区域

**工具（Tools）**：
- 职责单一、接口语义清晰
- 返回 token 友好的信息
- 精心甄别"最小可行工具集（MVTS）"

**示例（Few-shot）**：
- 提供多样且典型的示例
- 直接画像"期望行为"

---

## 3. 架构设计

### 3.1 GSSC 流水线

ContextBuilder 的核心是 **GSSC (Gather-Select-Structure-Compress)** 流水线：

```
用户查询 → [Gather] 多源信息汇集 → [Select] 智能信息选择 → [Structure] 结构化输出 → [Compress] 兜底压缩 → 优化上下文
```

**各阶段职责**：

1. **Gather（汇集）**：从多个来源（记忆、RAG、对话历史）收集候选信息
2. **Select（选择）**：根据相关性+新近性评分，筛选最有价值的信息
3. **Structure（结构化）**：组织成固定骨架的上下文模板
4. **Compress（压缩）**：对超限上下文进行兜底压缩

### 3.2 上下文模板结构

```markdown
[Role & Policies]
系统指令和行为准则

[Task]
当前需要完成的具体任务

[State]
Agent 的当前状态和上下文信息

[Evidence]
从外部知识库检索的证据信息

[Context]
历史对话和相关记忆

[Output]
期望的输出格式和要求
```

### 3.3 核心数据结构

**ContextPacket（候选信息包）**：
```python
@dataclass
class ContextPacket:
    content: str              # 信息内容
    timestamp: datetime       # 时间戳
    token_count: int          # Token 数量
    relevance_score: float    # 相关性分数(0.0-1.0)
    metadata: Dict            # 可选的元数据
```

**ContextConfig（配置管理）**：
```python
@dataclass
class ContextConfig:
    max_tokens: int = 3000        # 最大 token 数量
    reserve_ratio: float = 0.2    # 为系统指令预留的比例
    min_relevance: float = 0.1    # 最低相关性阈值
    enable_compression: bool = True
    recency_weight: float = 0.3   # 新近性权重
    relevance_weight: float = 0.7 # 相关性权重
```

---

## 4. 核心组件详解

### 4.1 ContextBuilder - 上下文构建器

`ContextBuilder` 是上下文工程的核心组件，实现 GSSC 流水线。

**主要方法**：
```python
from hello_agents.context import ContextBuilder, ContextConfig

# 创建构建器
builder = ContextBuilder(
    memory_tool=memory_tool,
    rag_tool=rag_tool,
    config=ContextConfig(max_tokens=3000)
)

# 构建上下文
context = builder.build(
    user_query="如何优化Pandas内存？",
    conversation_history=history,
    system_instructions="你是Python数据工程顾问"
)
```

**评分算法**：
```python
# 综合分数 = 相关性权重 × 相关性 + 新近性权重 × 新近性
combined_score = (
    config.relevance_weight * relevance_score +
    config.recency_weight * recency_score
)
```

### 4.2 NoteTool - 结构化笔记

`NoteTool` 为长时程任务提供结构化外部记忆，以 Markdown 文件为载体。

**核心操作**：
```python
from hello_agents.tools import NoteTool

note_tool = NoteTool(workspace_path="./workspace")

# 创建笔记
note_tool.execute("create", 
    title="Pandas内存优化",
    content="## 优化策略\n1. 使用category类型\n2. 分块读取"
)

# 搜索笔记
note_tool.execute("search", query="内存优化")

# 更新笔记
note_tool.execute("update",
    note_id="note_123",
    content="## 新增策略\n3. 使用nullable类型"
)
```

**笔记格式**：
```markdown
---
title: Pandas内存优化
created: 2026-07-06
updated: 2026-07-06
tags: [python, pandas, memory]
importance: 0.8
---

## 优化策略

1. 使用category类型替代object
2. 分块读取大文件
3. 使用nullable类型减少内存
```

### 4.3 TerminalTool - 即时文件系统访问

`TerminalTool` 支持智能体进行文件系统操作和即时上下文检索。

**核心功能**：
```python
from hello_agents.tools import TerminalTool

terminal = TerminalTool(workspace_path="./project")

# 列出文件
files = terminal.execute("list", path=".")

# 读取文件
content = terminal.execute("read", path="src/main.py")

# 搜索文件
results = terminal.execute("search", pattern="*.py", query="def main")

# 获取文件信息
info = terminal.execute("info", path="src/")
```

**即时上下文（JIT Context）**：
- 维护轻量化引用（文件路径、URL）
- 运行时通过工具动态加载
- 避免一次性加载所有数据

---

## 5. 完整案例：长时程代码助手

### 5.1 场景设定

**业务场景**：维护一个中型 Python Web 应用（Flask，约50个文件）

**挑战**：
1. 信息量超出上下文窗口 → 使用 TerminalTool 即时检索
2. 跨会话的状态管理 → 使用 NoteTool 记录进展
3. 上下文质量与相关性 → 使用 ContextBuilder 智能筛选

### 5.2 实现代码

```python
from hello_agents import SimpleAgent, HelloAgentsLLM
from hello_agents.context import ContextBuilder, ContextConfig
from hello_agents.tools import NoteTool, TerminalTool, MemoryTool

class CodeAssistantAgent(SimpleAgent):
    """具有上下文感知能力的代码助手"""
    
    def __init__(self, name, llm, **kwargs):
        super().__init__(name=name, llm=llm)
        
        # 初始化工具
        self.note_tool = NoteTool(workspace_path=kwargs.get("workspace", "."))
        self.terminal = TerminalTool(workspace_path=kwargs.get("workspace", "."))
        self.memory_tool = MemoryTool(user_id=kwargs.get("user_id", "default"))
        
        # 初始化上下文构建器
        self.context_builder = ContextBuilder(
            memory_tool=self.memory_tool,
            config=ContextConfig(max_tokens=4000)
        )
        
        self.conversation_history = []
    
    def run(self, user_input: str) -> str:
        """运行Agent，自动构建优化的上下文"""
        
        # 1. 使用TerminalTool探索代码库
        code_context = self._explore_codebase(user_input)
        
        # 2. 使用NoteTool获取相关笔记
        notes_context = self._get_relevant_notes(user_input)
        
        # 3. 构建优化的上下文
        optimized_context = self.context_builder.build(
            user_query=user_input,
            conversation_history=self.conversation_history,
            system_instructions="你是代码助手，专注于代码分析和重构建议",
            custom_packets=[code_context, notes_context]
        )
        
        # 4. 调用LLM
        messages = [
            {"role": "system", "content": optimized_context},
            {"role": "user", "content": user_input}
        ]
        response = self.llm.invoke(messages)
        
        # 5. 更新对话历史和笔记
        self._update_history(user_input, response)
        self._save_to_notes(user_input, response)
        
        return response
    
    def _explore_codebase(self, query):
        """使用TerminalTool探索代码库"""
        # 根据查询搜索相关文件
        results = self.terminal.execute("search", pattern="*.py", query=query)
        return results
    
    def _get_relevant_notes(self, query):
        """使用NoteTool获取相关笔记"""
        notes = self.note_tool.execute("search", query=query)
        return notes
    
    def _save_to_notes(self, question, answer):
        """将重要交互保存到笔记"""
        self.note_tool.execute("create",
            title=f"Q&A: {question[:50]}",
            content=f"**问题**: {question}\n\n**回答**: {answer}",
            tags=["qa", "code"]
        )
```

---

## 6. 最佳实践与优化建议

### 6.1 动态调整 token 预算

根据任务复杂度动态调整 `max_tokens`：
- 简单查询：2000 tokens
- 复杂分析：4000+ tokens

### 6.2 相关性计算优化

生产环境中，将简单的关键词重叠替换为向量相似度计算：
```python
# 简单实现（本章示例）
content_words = set(content.lower().split())
query_words = set(query.lower().split())
similarity = len(content_words & query_words) / len(content_words | query_words)

# 生产环境建议
# 使用 sentence-transformers 计算向量相似度
```

### 6.3 缓存机制

对于不变的系统指令和知识库内容，实现缓存：
```python
# 缓存系统指令
cached_system_prompt = None

def get_system_prompt():
    global cached_system_prompt
    if cached_system_prompt is None:
        cached_system_prompt = load_system_prompt()
    return cached_system_prompt
```

### 6.4 监控与日志

记录每次上下文构建的统计信息：
```python
# 统计信息
stats = {
    "total_packets": len(packets),
    "selected_packets": len(selected),
    "token_usage": current_tokens,
    "compression_ratio": current_tokens / max_tokens
}
```

---

## 7. 与前几章的关系

| 章节 | 内容 | 与本章关系 |
|------|------|-----------|
| 第七章 | 构建Agent框架 | 本章扩展 Agent 的上下文管理能力 |
| 第八章 | 记忆与检索 | 本章利用记忆系统提供上下文 |
| **第九章** | **上下文工程** | **当前章节** |
| 第十章 | 智能体通信协议 | 本章为后续协议集成奠定基础 |

---

## 8. 本项目实现差异

### 8.1 版本差异

教程要求 `hello-agents[all]==0.2.7`，本项目使用 `0.2.0`。

**影响**：
- `ContextBuilder`、`NoteTool`、`TerminalTool` 在 0.2.0 中可能不可用
- 需要检查实际安装的包是否包含这些组件

**解决方案**：
1. 升级到 0.2.7（需要用户确认）
2. 或基于现有组件实现等价功能

### 8.2 模型配置

教程示例可能使用 GPT 模型，本项目使用 Kimi K2.6：
```python
# 教程写法
model="gpt-4o-mini"

# 本项目写法
model=os.getenv("OPENAI_MODEL")  # kimi-k2.6
```

---

## 9. 运行方式

### 9.1 环境检查

```bash
# 检查 hello-agents 版本
pip show hello-agents

# 如果版本低于 0.2.7，需要升级
pip install "hello-agents[all]==0.2.7"
```

### 9.2 运行示例代码

```bash
# 进入章节目录
cd chapter09

# 运行 ContextBuilder 示例
python code/context_builder_demo.py

# 运行 NoteTool 示例
python code/note_tool_demo.py

# 运行 TerminalTool 示例
python code/terminal_tool_demo.py

# 运行完整案例
python code/code_assistant.py
```

### 9.3 环境变量配置

确保 `.env` 文件包含：
```bash
# 大模型配置
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://kimi.a7m.com.cn/v1
OPENAI_MODEL=kimi-k2.6
```

---

## 10. 学习建议

### 10.1 重点理解

1. **GSSC 流水线**：理解四个阶段的职责和实现
2. **评分算法**：为什么使用相关性+新近性的加权组合？
3. **即时上下文**：与传统预计算检索的区别
4. **结构化笔记**：如何维持跨会话的连贯性

### 10.2 实验建议

1. **修改权重参数**：调整 `recency_weight` 和 `relevance_weight`，观察上下文变化
2. **对比不同压缩策略**：测试分区压缩 vs. 简单截断的效果
3. **NoteTool 实践**：创建多个笔记，测试搜索和关联功能
4. **TerminalTool 探索**：在真实项目中使用即时上下文检索

### 10.3 常见问题

**Q: 上下文工程和提示工程有什么区别？**
A: 提示工程关注如何写好提示词，上下文工程关注如何管理整个上下文窗口的所有信息（包括提示、工具、历史、外部数据等）。

**Q: 为什么需要即时上下文（JIT）？**
A: 大型项目无法一次性加载所有代码到上下文窗口。JIT 允许按需加载，只在需要时查看具体文件。

**Q: NoteTool 和 MemoryTool 有什么区别？**
A: MemoryTool 主要管理对话式记忆（工作、情景、语义记忆），NoteTool 提供结构化的项目式笔记，更适合长期追踪和任务管理。

---

## 11. 参考来源

- **教程文档**: [Hello-Agents 第九章](https://github.com/datawhalechina/hello-agents/blob/main/docs/chapter9/%E7%AC%AC%E4%B9%9D%E7%AB%A0%20%E4%B8%8A%E4%B8%8B%E6%96%87%E5%B7%A5%E7%A8%8B.md)
- **框架源码**: `hello_agents.context`、`hello_agents.tools` 模块
- **论文参考**:
  - [1] Context Engineering for LLMs
  - [2] Attention is All You Need (Transformer)

---

**下一步**: 阅读 `code/` 目录下的示例代码，动手实验上下文工程功能。