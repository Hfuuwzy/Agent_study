# 第九章学习笔记：上下文工程

> **完成时间**: 2026-08-21
> **教程**: [Hello-Agents 第九章 上下文工程](https://github.com/datawhalechina/hello-agents/blob/main/docs/chapter9/%E7%AC%AC%E4%B9%9D%E7%AB%A0%20%E4%B8%8A%E4%B8%8B%E6%96%87%E5%B7%A5%E7%A8%8B.md)
> **框架版本**: hello-agents 0.2.8

---

## 1. 核心收获

### 1.1 上下文工程 vs. 提示工程

| 维度 | 提示工程 | 上下文工程 |
|------|----------|------------|
| 关注点 | 写好单条提示词 | 策划维护整个上下文窗口的信息集合 |
| 范围 | system prompt、用户输入 | 提示 + 工具输出 + 记忆 + RAG + 历史 |
| 时间维度 | 单轮优化 | 跨多轮的状态管理 |

关键转变：从"怎么写好一句话"到"每次调用前如何以可复用、可度量、可演进的方式拼装输入"。

### 1.2 上下文腐蚀（Context Rot）

- token 越多 ≠ 效果越好。注意力被"拉薄"，模型准确回忆信息的能力随上下文变长而下降。
- 上下文是**有限资源**，存在边际收益递减——这是 GSSC 中 Select/Compress 阶段存在的根本原因。

### 1.3 GSSC 流水线

```
Gather(多源汇集) → Select(相关性+新近性评分筛选) → Structure(固定骨架模板) → Compress(超限兜底压缩)
```

实测输出的六段式骨架：

```markdown
[Role & Policies]  系统指令
[Task]             用户问题
[State]            记忆检索结果（关键进展与未决问题）
[Evidence]         RAG 检索结果（事实与引用）
[Context]          对话历史
[Output]           输出格式要求
```

### 1.4 三个新组件的分工

- **ContextBuilder**：GSSC 流水线执行者，综合分数 = `relevance_weight × 相关性 + recency_weight × 新近性`
- **NoteTool**：Markdown 文件载体的结构化笔记，跨会话项目状态（区别于 MemoryTool 的对话式记忆）
- **TerminalTool**：文件系统即时访问，JIT Context 思想——只存轻量引用（路径/URL），运行时按需加载

---

## 2. 实践记录

### 2.1 环境

- 按 MEMORY.md 6.1 新基线升级到 hello-agents 0.2.8（移除 gradio/autogen 冲突源，pip check 通过）。

### 2.2 ContextBuilder_test.py 全流程验证

**Part 1 — ContextBuilder 独立测试**：
- MemoryTool 添加语义记忆 + 情景记忆成功（Qdrant 云 + Neo4j 云）
- RAGTool 从 `./knowledge_base` 检索返回 5 条结果
- `builder.build()` 输出完整六段式上下文

**Part 2 — ContextAwareAgent 完整调用**：

```python
class ContextAwareAgent(SimpleAgent):
    def run(self, user_input):
        optimized_context = self.context_builder.build(...)   # GSSC
        messages = [{"role": "system", "content": optimized_context},
                    {"role": "user", "content": user_input}]
        response = self.llm.invoke(messages)                  # Kimi K2.6
        self.conversation_history.append(...)                 # 更新历史
        self.memory_tool.run({"action": "add", ...})          # 写回记忆
        return response
```

- LLM 返回高质量 Pandas 内存优化方案，**严格遵循 [Output] 四段模板**：结论 → 依据 → 风险与假设 → 下一步行动建议
- 交互自动写回情景记忆，形成闭环

### 2.3 运行注意事项

- Windows 控制台必须 `$env:PYTHONIOENCODING="utf-8"`，否则框架 print emoji 直接崩溃（见 Bug 3）

---

## 3. Bug 修复记录

### Bug 1: load_dotenv() 时序问题（已记入 MEMORY.md 8.8）

- **现象**：创建 MemoryTool 崩溃，`Qdrant连接失败: localhost:6331 拒绝连接`
- **根因**：框架 `database_config.py` 在 import 时初始化 `db_config`；若用户 `load_dotenv()` 在 import 之后，配置已固化为空
- **修复**：`load_dotenv()` 放在所有 hello_agents import 之前

### Bug 2: 中文相关性评分失效 → 记忆/RAG 结果被全过滤

- **现象**：`min_relevance` 默认 0.3 时，中文记忆和 RAG 结果全部消失
- **根因**：框架 `_select()` 用 `content.lower().split()` 做关键词重叠评分——中文无空格，整句成一个 token，与查询词交集≈0，relevance_score≈0
- **修复**：`ContextConfig(min_relevance=0.0)` 绕过过滤
- **教训**：用户在文件下半部分新增 `ContextAwareAgent` 时，其内部 `ContextBuilder(config=ContextConfig(max_tokens=4000))` **漏掉了同样的修复**，需要同步补上——同一坑在一处修了不等于处处修了

### Bug 3: Windows GBK 编码崩溃

- **现象**：`RAGTool.__init__` 抛 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2705'`
- **根因**：框架用 `print("✅ ...")` 输出初始化信息，Windows 控制台默认 GBK 编不了 emoji；更糟的是异常处理分支里 `print("❌ ...")` 会再次抛同样异常，掩盖原始错误
- **修复**：运行前设置 `$env:PYTHONIOENCODING="utf-8"`

---

## 4. 代码对齐差异

| 项目 | 教程写法 | 本项目实现 | 对齐状态 |
|------|----------|-----------|---------|
| 框架版本 | `hello-agents[all]==0.2.7` | `0.2.8`（新章节优先基线） | 功能等价 |
| LLM | GPT 系列 | Kimi K2.6（`.env` 读取） | 功能等价 |
| ContextConfig | 默认参数 | 增加 `min_relevance=0.0` | 环境适配（中文分词问题） |
| 测试脚本 | 教程片段分散演示 | `ContextBuilder_test.py` 组合 Part1+Part2 | 功能等价 |

已知未对齐项（环境数据问题，非代码问题）：
- `./knowledge_base` 内容是 Happy-LLM PDF，与测试查询（Pandas）无关 → [Evidence] 段落质量有限
- Qdrant 云集合有历史测试残留（"李四是前端工程师"混入 [State]）

---

## 5. 深度思考

1. **上下文质量取决于最差的信息源**。[State] 里一条无关记忆、[Evidence] 里五段不相关 PDF 引文，都会稀释真正有用的信号——这正是 Context Rot 的微观体现。GSSC 解决"结构"问题，但解决不了"数据卫生"问题。

2. **Select 阶段的评分算法是本章最弱一环**。关键词重叠对英文勉强可用，对中文完全失效。生产化路径：换 embedding 余弦相似度（README 6.2 也指出了这一点）。这次 `min_relevance=0.0` 只是绕过，不是修复。

3. **[Output] 格式模板对 LLM 输出结构的约束力很强**。实测 Kimi K2.6 严格按四段模板输出，说明 Structure 阶段投入产出比很高——比在用户消息里反复强调格式可靠得多。

4. **JIT Context 是应对大代码库的唯一现实解**。50 个文件的 Flask 项目不可能整体塞进窗口，TerminalTool 的"轻量引用 + 运行时加载"模式与人类工程师查代码的方式同构。

---

## 6. 下一步计划

1. 清理 Qdrant 云 `hello_agents_vectors` 集合的历史测试数据，消除记忆污染
2. 将 `knowledge_base` 替换为领域相关文档（如 Pandas 官方文档切片），验证 [Evidence] 真正生效时的效果
3. 实验：调整 `recency_weight`/`relevance_weight` 权重对比上下文变化；对比分区压缩 vs 简单截断
4. 进入第十章：智能体通信协议
