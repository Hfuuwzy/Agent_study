# Agent_study - 智能体学习项目

> 基于 [Hello-Agents](https://github.com/datawhalechina/hello-agents) 教程的智能体学习实践项目

---

## 📋 项目简介

本项目是跟随 Datawhale Hello-Agents 教程的完整学习记录，从智能体基础概念到完整框架开发，系统学习 LLM 驱动的智能体（Agent）技术栈。

**学习目标：**
- 理解智能体的核心概念与架构设计
- 掌握 ReAct、Reflection、Plan-and-Solve 等经典范式
- 动手实现记忆系统、RAG 检索、多智能体协作
- 构建可扩展的智能体框架

---

## 🛠️ 环境配置

### 1. 基础环境

```bash
# Python 版本
python >= 3.11

# 创建 conda 环境
conda create -n agent_study python=3.11
conda activate agent_study
```

### 2. 核心依赖安装

```bash
# 安装 Hello-Agents 框架（包含所有依赖）
pip install "hello-agents[all]==0.2.0"

# 安装 spaCy 中文/英文模型
python -m spacy download zh_core_web_sm
python -m spacy download en_core_web_sm

# 其他常用依赖
pip install python-dotenv requests
```

### 3. 环境变量配置 (.env)

在项目根目录创建 `.env` 文件：

```bash
# ==================== 大模型配置 ====================
# OpenAI 兼容 API（推荐 kimi-k2.6）
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://kimi.a7m.com.cn/v1
OPENAI_MODEL=kimi-k2.6

# ==================== 向量数据库 ====================
# Qdrant Cloud（推荐）
QDRANT_URL=https://your-cluster.qdrant.tech:6333
QDRANT_API_KEY=your_qdrant_key

# ==================== 图数据库 ====================
# Neo4j Aura（推荐）
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

# ==================== Embedding 配置 ====================
# 方案1: DashScope（推荐，无需本地模型）
EMBED_MODEL_TYPE=dashscope
EMBED_API_KEY=your_dashscope_key
EMBED_MODEL_NAME=text-embedding-v3

# 方案2: 本地模型（需要下载）
# EMBED_MODEL_TYPE=local
# EMBED_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2

# ==================== Hugging Face 配置 ====================
# 模型缓存目录（可选）
HF_HOME=D:\HF
SENTENCE_TRANSFORMERS_HOME=D:\HF\hub
TRANSFORMERS_CACHE=D:\HF\hub

# 镜像加速（国内可选，但可能不稳定）
# HF_ENDPOINT=https://hf-mirror.com
```

### 4. 代理配置（中国大陆用户）

```bash
# 如果使用 Clash/Clash Verge 代理
# 确保 TUN 模式或系统代理已开启
# 推荐节点：香港专线（对 6333/7687 端口支持好）
```

---

## ⚠️ 常见坑点与解决方案

### 坑点 1: qdrant-client 版本不兼容

**现象：**
```
ERROR: 'QdrantClient' object has no attribute 'search'
ERROR: 'CollectionInfo' object has no attribute 'vectors_count'
```

**原因：** `hello-agents 0.2.0` 依赖旧版 qdrant-client API，新版已移除 `.search()` 方法

**解决：**
```bash
# 降级到兼容版本
pip install "qdrant-client==1.11.0"
```

### 坑点 2: Hugging Face 模型下载失败

**现象：**
```
Error: sentence-transformers/all-MiniLM-L6-v2 does not appear to have a file named pytorch_model.bin
```

**原因：** 网络问题导致模型下载不完整

**解决：**
```bash
# 方法1: 使用 DashScope 替代（推荐）
# 修改 .env: EMBED_MODEL_TYPE=dashscope

# 方法2: 手动下载（需要代理）
$env:HF_HOME="D:\HF"
hf download sentence-transformers/all-MiniLM-L6-v2 --cache-dir "D:\HF\hub"

# 方法3: 清理缓存重新下载
Remove-Item -Recurse -Force "$env:HF_HOME\hub\models--sentence-transformers--all-MiniLM-L6-v2"
```

### 坑点 3: 代理软件导致端口不通

**现象：**
```
SSL/TLS connection failed
Unable to retrieve routing information
```

**原因：** Clash Verge 对某些节点的高端口（6333/7687）支持不好

**解决：**
- 换用普通 Clash 而非 Clash Verge
- 或切换到香港专线节点
- 确保 TUN 模式已开启

### 坑点 4: spaCy 模型未安装

**现象：**
```
OSError: [E050] Can't find model 'zh_core_web_sm'
```

**解决：**
```bash
python -m spacy download zh_core_web_sm
python -m spacy download en_core_web_sm
```

### 坑点 5: TF-IDF 模型未训练

**现象：**
```
WARNING: TF-IDF模型未训练，请先调用fit()方法
```

**原因：** Embedding 模型加载失败，fallback 到 TF-IDF，但 RAG 知识库为空

**解决：**
- 确保 Embedding 配置正确（DashScope 或本地模型）
- 先运行 `fast_rag.py` 添加知识到知识库

---

## 📚 章节概览

| 章节 | 主题 | 核心内容 | 状态 |
|------|------|----------|------|
| [第一章](chapter01/) | 初识智能体 | 智能体概念、分类、PEAS模型、Thought-Action-Observation协议 | ✅ 已完成 |
| [第二章](chapter02/) | 智能体发展史 | ELIZA、SHRDLU、专家系统、强化学习、LLM智能体演进 | ✅ 已完成 |
| [第三章](chapter03/) | 大语言模型基础 | Transformer架构、注意力机制、分词技术、N-gram语言模型 | ✅ 已完成 |
| [第四章](chapter04/) | 智能体经典范式 | ReAct、Plan-and-Solve、Reflection、多智能体协作 | ✅ 已完成 |
| [第五章](chapter05/) | 低代码平台搭建 | Coze、Dify、FastGPT等平台实践 | ✅ 已完成 |
| [第六章](chapter06/) | 框架开发实践 | 三步问答助手、工具系统、Agent核心循环 | ✅ 已完成 |
| [第七章](chapter07/) | 构建Agent框架 | SimpleAgent、ToolRegistry、ReActAgent完整实现 | ✅ 已完成 |
| [第八章](chapter08/) | 记忆与检索 | 四种记忆类型、RAG系统、向量数据库、知识图谱 | ✅ 已完成 |

---

## 📖 各章节详细说明

### 第一章：初识智能体
**核心概念：**
- 智能体的四个基本要素：环境、传感器、执行器、自主性
- 智能体分类：反射式、模型反射式、目标式、效用式、学习式
- LLM驱动智能体的核心能力：规划、工具使用、动态修正

**实践内容：**
- 构建第一个智能旅行助手
- 实现 Thought-Action-Observation 循环
- 天气查询 + 景点推荐工具链

**关键代码：** `chapter01/code/travel_assistant.py`

---

### 第二章：智能体发展史
**核心概念：**
- 符号主义 AI：ELIZA、SHRDLU、专家系统
- 连接主义 AI：神经网络、深度学习
- 行为主义 AI：强化学习、进化算法
- 现代范式：LLM + 工具 + 记忆

**实践内容：**
- 复现 ELIZA 心理治疗机器人
- 理解符号推理与神经网络的区别

**关键代码：** `chapter02/code/eliza.py`

---

### 第三章：大语言模型基础
**核心概念：**
- Transformer架构：Self-Attention、多头注意力
- 分词技术：BPE、WordPiece、Unigram
- 语言模型：N-gram、神经网络LM、预训练LM

**实践内容：**
- 实现简化版 Transformer
- BPE分词算法实现
- N-gram概率计算

**关键代码：**
- `chapter03/code/transformer.py`
- `chapter03/code/bpe.py`
- `chapter03/code/ngram.py`

---

### 第四章：智能体经典范式
**核心概念：**
- **ReAct**: 推理 + 行动交替进行
- **Plan-and-Solve**: 先规划后执行
- **Reflection**: 自我反思与修正
- **多智能体**: 协作与竞争

**实践内容：**
- 实现 ReAct Agent（推理-行动循环）
- 实现 Plan-and-Solve Agent（规划-执行）
- 实现 Reflection Agent（自我反思）

**关键代码：**
- `chapter04/code/react_agent.py`
- `chapter04/code/plan_solve_agent.py`
- `chapter04/code/reflection_agent.py`

---

### 第五章：低代码平台搭建
**核心概念：**
- Coze：字节跳动的智能体开发平台
- Dify：开源 LLM 应用开发平台
- FastGPT：基于 RAG 的知识库问答系统

**实践内容：**
- 在 Coze 上搭建旅游助手
- 使用 Dify 构建知识库问答
- FastGPT 本地部署与配置

**关键文件：** `chapter05/NOTES.md`

---

### 第六章：框架开发实践
**核心概念：**
- Agent 核心循环：感知 → 思考 → 行动 → 观察
- 工具系统：Tool 抽象、ToolRegistry
- 提示工程：System Prompt、Few-shot

**实践内容：**
- 三步问答助手实现
- 工具注册与调用机制
- LLM 客户端封装

**关键代码：** `chapter06/code/`

---

### 第七章：构建Agent框架
**核心概念：**
- SimpleAgent：基础 Agent 实现
- ToolRegistry：工具注册表
- ReActAgent：完整 ReAct 循环
- 消息历史管理

**实践内容：**
- 完整 Agent 框架实现
- 多工具链组合
- 复杂任务拆解

**关键代码：** `chapter07/code/myagents/`

---

### 第八章：记忆与检索 🔄 学习中
**核心概念：**
- **四种记忆类型：**
  - 工作记忆（WorkingMemory）：临时对话上下文
  - 情景记忆（EpisodicMemory）：历史交互事件
  - 语义记忆（SemanticMemory）：知识图谱存储
  - 感知记忆（PerceptualMemory）：多模态信息
- **RAG系统：** 检索增强生成
  - 文档向量化
  - 向量检索（Qdrant）
  - 混合检索策略（MQE、HyDE）

**技术栈：**
- 向量数据库：Qdrant
- 图数据库：Neo4j
- 嵌入服务：DashScope / sentence-transformers
- 文本处理：spaCy

**实践内容：**
- 记忆系统实现与测试
- RAG 知识库构建
- 记忆 + RAG 组合应用

**关键代码：**
- `chapter08/code/test_env.py` - 环境测试
- `chapter08/code/fast_memory.py` - 快速记忆测试
- `chapter08/code/fast_rag.py` - RAG 知识库测试
- `chapter08/code/fast_assistant.py` - 完整助手
- `chapter08/code/test.py` / `demo_combined.py` - 综合演示

**当前进展：**
- ✅ Qdrant 向量数据库连接成功
- ✅ Neo4j 图数据库连接成功
- ✅ sentence-transformers 模型下载完成
- ✅ spaCy 中英文模型加载成功
- ⚠️ qdrant-client 版本降级到 1.11.0 以兼容 hello-agents
- 🔄 正在测试记忆搜索与 RAG 检索功能

---

## 🚀 快速开始

### 运行环境测试

```powershell
# 激活环境
conda activate agent_study

# 测试环境配置
python chapter08/code/test_env.py

# 测试记忆系统
python chapter08/code/fast_memory.py

# 测试 RAG 系统
python chapter08/code/fast_rag.py
```

### 运行完整演示

```powershell
# 综合演示（需要完整配置 .env）
python chapter08/code/test.py

# 或
python chapter08/code/demo_combined.py
```

---

## 📁 项目结构

```
Agent_study/
├── .env                          # 环境变量配置（不提交）
├── .gitignore                    # Git 忽略规则
├── MEMORY.md                     # 项目流程记忆文档
├── README.md                     # 本文件
├── chapter01/                    # 第一章：初识智能体
│   ├── README.md
│   ├── NOTES.md
│   └── code/
├── chapter02/                    # 第二章：智能体发展史
│   ├── README.md
│   ├── NOTES.md
│   └── code/
├── chapter03/                    # 第三章：大语言模型基础
│   ├── README.md
│   ├── NOTES.md
│   └── code/
├── chapter04/                    # 第四章：智能体经典范式
│   ├── README.md
│   ├── NOTES.md
│   └── code/
├── chapter05/                    # 第五章：低代码平台搭建
│   ├── README.md
│   ├── NOTES.md
│   └── code/
├── chapter06/                    # 第六章：框架开发实践
│   ├── README.md
│   ├── NOTES.md
│   └── code/
├── chapter07/                    # 第七章：构建Agent框架
│   ├── README.md
│   ├── NOTES.md
│   └── code/
├── chapter08/                    # 第八章：记忆与检索 ✅
│   ├── README.md
│   ├── NOTES.md
│   └── code/
├── knowledge_base/               # RAG 知识库目录
├── memory_data/                  # 记忆数据存储
└── notes/                        # 学习笔记附件
```

---

## 📝 更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-07-06 | 完成第八章：记忆与检索，解决环境迁移全套问题，PDF入库+GPU加速+RAG检索全流程跑通 |
| 2026-07-05 | 创建项目 README.md，记录环境配置与常见坑点 |
| 2026-07-05 | 完成第八章环境配置，解决 qdrant-client 版本兼容问题 |

---

## 🔗 参考资源

- **教程源码**: [Hello-Agents](https://github.com/datawhalechina/hello-agents)
- **框架文档**: [hello-agents 文档](https://github.com/datawhalechina/hello-agents/tree/main/docs)
- **Datawhale**: [Datawhale 官网](https://www.datawhale.club/)

---

## 💡 学习建议

1. **按顺序学习**：每章都建立在前一章基础上
2. **动手实践**：不要只看，要跑代码、改代码
3. **记录笔记**：每章学完更新 `NOTES.md`
4. **遇到问题**：先查本 README 的「常见坑点」
5. **扩展实验**：尝试修改参数、添加新功能

---

**Happy Learning! 🚀**
