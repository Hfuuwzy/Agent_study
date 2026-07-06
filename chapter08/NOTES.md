# 第八章学习笔记：记忆与检索

> 完成时间：2026-07-06
> 章节目标：理解并实践 Memory 系统和 RAG 检索增强生成

---

## 1. 核心收获

### 1.1 Memory 记忆系统

人类记忆的多层结构在 Agent 中的映射：

| 记忆类型 | 特点 | 存储介质 | 典型用途 |
|---------|------|---------|---------|
| **Working Memory** | 短期、容量有限(7±2) | Python内存/SQLite | 当前问题、临时上下文 |
| **Episodic Memory** | 事件序列、可检索 | SQLite + Qdrant + Neo4j | 学习历史、交互记录 |
| **Semantic Memory** | 概念知识、结构化 | Neo4j图数据库 | 知识点、用户画像 |
| **Perceptual Memory** | 多模态(文本/图像/音频) | Qdrant向量存储 | 多媒体信息 |

**关键理解**：
- MemoryTool 是统一接口，屏蔽了底层存储细节
- 不同记忆类型适合不同场景：短期上下文用 Working，历史记录用 Episodic，知识概念用 Semantic
- 评分公式：`score = (similarity × weight + recency × weight) × importance`

### 1.2 RAG 检索增强生成

完整流程：
```
PDF → MarkItDown提取文本 → 智能分块 → Embedding向量化 → Qdrant存储
用户问题 → Embedding → 向量检索 → Top-K片段 → 上下文构建 → LLM生成答案
```

**高级检索技术**：
- **MQE (Multi-Query Expansion)**：将一个问题扩展成多个相关问题，提高召回率
- **HyDE (Hypothetical Document Embeddings)**：生成假设文档嵌入，提高检索精度

**权衡**：
- 普通检索：快，但可能漏掉相关内容
- MQE+HyDE：慢(3次LLM调用)，但更准确

### 1.3 外部数据库架构

实际使用的技术栈：
- **Qdrant**：向量数据库，存储 embedding，支持相似度检索
- **Neo4j**：图数据库，存储语义关系，支持知识图谱
- **SQLite**：轻量级文档存储，存储原始文本
- **sentence-transformers**：本地 embedding 模型(all-MiniLM-L6-v2, 384维)

**为什么不用纯内存？**
- 持久化：程序重启后数据不丢失
- 大规模：可以存储数百万文档片段
- 专业化：向量检索、图遍历、关系查询都有优化

---

## 2. 实践记录

### 2.1 成功验证的部分

1. **环境配置** ✅
   - `.env` 配置正确，包含 Qdrant、Neo4j、LLM、Embedding 等全部配置
   - 云数据库连接成功

2. **工具初始化** ✅
   ```
   MemoryManager 初始化成功
   RAGTool 初始化成功
   Qdrant 连接成功
   Neo4j 连接成功
   Embedding 模型加载成功
   ```

3. **核心概念理解** ✅
   - 四种记忆类型的区别和应用场景
   - RAG 的工作流程和每个环节的作用
   - Memory + RAG 的组合价值

### 2.2 遇到的问题

#### 问题1：RAGTool.execute 返回值格式不匹配

**现象**：
```python
result = rag_tool.execute("add_document", ...)
if result.get("success", False):  # AttributeError: 'str' object has no attribute 'get'
```

**原因**：实际返回的是字符串，不是字典。

**解决**：需要适配实际返回值格式，或者使用 try-except 处理。

### 3.2 新电脑环境迁移问题（2026-07-05 ~ 07-06）

本次会话解决了从旧电脑迁移到新电脑后的整套环境问题：

#### 问题1：qdrant-client 版本不兼容

**现象**：`'QdrantClient' object has no attribute 'search'`

**原因**：`hello-agents==0.2.0` 调用 `client.search()` 方法，但 qdrant-client 1.17+/1.18+ 已移除该方法，改用 `query_points()`。

**解决**：降级到 `qdrant-client==1.11.0`，同时保留 `query_points` 方法，双方法兼容。

#### 问题2：HuggingFace 模型下载失败

**现象**：`hf-mirror.com` 返回 308 跳转，huggingface_hub 元数据校验失败。

**原因**：镜像站对 `/resolve/` 请求返回 308 跳回 huggingface.co，不兼容 huggingface_hub 客户端。

**解决**：移除 `.env` 中 `HF_ENDPOINT=https://hf-mirror.com`，保留 `HF_HOME=D:\HF`，通过 Clash 代理从 HuggingFace 官网直接下载。模型已完整缓存到 `D:\HF\hub\models--sentence-transformers--all-MiniLM-L6-v2`（87MB）。

#### 问题3：PyTorch GPU 安装

**现象**：从 `llm2vec` 环境（Python 3.10 + torch 2.7.0+cu128）复制 torch 包后报 `WinError 126`。

**原因**：Python 3.10 和 3.11 的 CPython ABI 不兼容，二进制包不能跨版本复制。

**解决**：恢复原 torch 备份，用 pip 安装对应 Python 3.11 的版本：`pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128`。最终安装 `torch==2.11.0+cu128`，`torch.cuda.is_available() = True`。

#### 问题4：GPU Embedding 加速

**现象**：默认走 CPU 编码，RTX 5070 显卡闲置。

**解决**：在 `fast_assistant.py` 中新增 `configure_gpu_embedder()` 函数，monkey-patch `LocalTransformerEmbedding` 类，将模型加载到 `cuda:0`，batch_size 提升到 128。验证：`model device: cuda:0`，显存占用 95.8MB，128 x 384 编码成功。

**原则**：不修改 `hello_agents` 包源码（site-packages），所有优化在项目代码里实现。

#### 问题5：PDF 处理 MissingDependencyException

**现象**：`PdfConverter threw MissingDependencyException: dependencies needed to read .pdf files have not been installed`

**原因**：MarkItDown 未安装 PDF 插件。

**解决**：`pip install "markitdown[pdf]"`，安装后 PDF 提取正常工作。

#### 问题6：RAGTool 返回值类型不匹配

**现象**：`AttributeError: 'str' object has no attribute 'get'`

**原因**：`RAGTool._add_document()` 返回字符串（如 `"✅ 文档已添加到知识库: ..."`），但 `fast_assistant.py` 用 `.get("success", False)` 把它当字典处理。

**解决**：改为检查字符串是否包含 `"✅"` 判断成功，用正则从 `"📊 分块数量: 94"` 提取 chunk 数。

#### 问题7：Neo4j 连接不稳定（已忽略）

**现象**：退出时报 `Failed to read from defunct connection` 和 `Unable to retrieve routing information`。

**原因**：Clash fake-ip（`198.18.x.x`）导致 Neo4j Bolt 连接（7687端口）长时间空闲后断开。

**处理**：不影响核心功能（PDF 入库、RAG 检索、Qdrant 向量搜索都正常），退出时的统计查询可忽略。

---

## 3. Bug 修复记录

### 3.1 fast_assistant.py 修复

1. **导入路径**
   ```python
   # 错误
   from hello_agents import MemoryTool, RAGTool
   
   # 正确
   from hello_agents.tools import MemoryTool, RAGTool
   ```

2. **PDF 路径**
   ```python
   # 错误：假设在 chapter08/notes/
   
   # 正确：实际在根目录 notes/
   pdf_path = os.path.join(
       os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
       "notes", "Happy-LLM-0727.pdf"
   )
   ```

3. **返回值适配**
   - 预期：`result.get("success")` 
   - 实际：返回字符串
   - 修复：需要根据实际情况处理返回值

---

## 4. 代码对齐差异

### 4.1 与教程一致的部分

- MemoryTool 和 RAGTool 的基本使用方式
- 记忆类型的概念和分类
- RAG 的工作流程设计

### 4.2 本项目环境的差异

| 方面 | 教程 | 本项目 |
|-----|------|--------|
| 模型 | 未明确 | Kimi-k2.6 |
| Embedding | DashScope | 本地 sentence-transformers |
| Qdrant | 本地 Docker | 云服务 |
| Neo4j | 本地 Docker | 云服务 |
| PDF 路径 | chapter08/notes/ | 根目录 notes/ |
| API 版本 | 可能较新 | hello_agents==0.2.0 |

### 4.3 关键差异点

1. ** Embedding 选择**
   - 教程：DashScope 云端 embedding
   - 本项目：本地 `sentence-transformers/all-MiniLM-L6-v2`
   - 影响：首次加载需要下载模型(~80MB)，后续本地运行

2. **数据库部署**
   - 教程：本地 Docker
   - 本项目：云服务
   - 影响：无需本地部署，但有网络依赖

3. **API 兼容性**
   - 教程代码和实际安装包有差异
   - 需要以实际源码为准

---

## 5. 深度思考

### 5.1 Memory + RAG 的真正价值

第八章不是简单教两个工具怎么用，而是展示了 Agent 从"单轮对话"到"持续学习系统"的演进：

**之前(第七章)**：
```
输入 → Agent → LLM → 输出 (无状态)
```

**之后(第八章)**：
```
输入 → [检索记忆 + 检索知识库] → LLM → 输出 → [写入记忆]
               ↑                              ↓
               └────── 持续学习和积累 ────────┘
```

这才是真正的"智能体"和"聊天机器人"的区别。

### 5.2 工程现实 vs 理想设计

学习过程中的一个重要认知：**框架设计和工程实现之间有巨大鸿沟**。

- 框架设计：优雅、模块化、可扩展
- 工程现实：慢、资源消耗大、API 不一致、文档滞后

但这不影响学习价值。理解设计思想比跑通代码更重要。

### 5.3 什么情况下不需要外部数据库？

之前我错误地想简化成本地内存版，虽然方向错了，但思考过程有价值：

**不需要外部数据库的场景**：
- 演示/测试：少量文档，临时使用
- 个人笔记：几十篇文档，单机使用
- 原型验证：快速验证概念

**必须使用外部数据库的场景**：
- 生产环境：数据不能丢失
- 大规模：百万级文档
- 多用户：需要隔离和权限
- 高性能：需要专门优化的向量检索

第八章属于后者，所以保留完整架构是对的。

---

## 6. 下一步计划

### 6.1 第九章预告

根据教程结构，第九章可能是：
- 多 Agent 协作
- Agent 编排
- 工作流设计
- 或者项目实战

### 6.2 待验证假设

1. **MQE + HyDE 的实际效果**：在真实文档上对比普通检索和高级检索的准确率
2. **不同 embedding 模型的影响**：all-MiniLM-L6-v2 vs DashScope vs OpenAI 的效果对比
3. **记忆衰减策略**：长期使用的记忆系统如何管理存储空间

### 6.3 可扩展方向

1. **异步处理**：PDF 入库改为异步，避免阻塞
2. **增量更新**：只处理新增或修改的文档，而非全量重新索引
3. **多模态 RAG**：支持图片、表格、视频的检索
4. **记忆可视化**：Neo4j 图数据的可视化展示
5. **用户画像**：基于 Semantic Memory 生成用户学习画像

---

## 7. 附录

### 7.1 关键文件

- `chapter08/code/fast_assistant.py` - 文档问答助手实现（含 GPU embedding monkey-patch）
- `chapter08/code/test_env.py` - HF 模型加载验证
- `chapter08/code/fast_memory.py` - 最小记忆测试
- `chapter08/code/fast_rag.py` - 最小 RAG 入库测试
- `chapter08/README.md` - 章节学习指南
- `.env` - 环境配置（含 API 密钥，不上传）
- `README.md` - 项目级 README，含环境配置与常见坑点

### 7.2 不上传的文件

```
.env                          # API 密钥
memory_data/                  # SQLite 数据
knowledge_base/               # RAG 数据
learning_report_*.json        # 学习报告
__pycache__/                  # Python 缓存
D:\HF\hub\                    # 本地模型缓存（11GB+）
```

### 7.3 运行命令

```bash
# 激活环境
conda activate agent_study

# 运行文档问答助手
python chapter08/code/fast_assistant.py

# 环境版本
# qdrant-client==1.11.0（降级兼容 hello-agents）
# torch==2.11.0+cu128（RTX 5070 GPU 加速）
# hello-agents==0.2.0
# markitdown[pdf]（含 PDF 插件）
```

---

## 8. 总结

第八章完成了从"对话机器人"到"知识助手"的跨越。

**核心能力获得**：
- ✅ 理解记忆系统的分层设计
- ✅ 理解 RAG 的完整流程
- ✅ 掌握 MemoryTool 和 RAGTool 的使用
- ✅ 了解外部数据库(Qdrant/Neo4j/SQLite)的作用
- ✅ 理解 MQE/HyDE 高级检索技术
- ✅ 明确工程实现中的现实问题(embedding 慢、API 差异等)

**本章最大的价值**：
不是跑通了某个代码，而是理解了 Agent 应用如何从"单次问答"升级为"持续学习、可检索外部知识、记住用户历史的智能系统"。

准备进入第九章。
