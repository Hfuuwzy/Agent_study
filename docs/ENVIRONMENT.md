# 环境配置与故障排查手册

> 本文件集中维护稳定的环境知识，供排查版本、配置与兼容性问题时查阅。用户红线与不可重复的教训见 `../MEMORY.md`。
>
> 更新日期:2026-08-25

---

## 1. 环境变量 (.env)

项目根目录的 `.env` 是运行所有脚本的前置条件。所有密钥一律使用占位符,真实值只在你的本地 `.env` 中出现。

```bash
# ==================== 大模型配置 ====================
# OpenAI 兼容接口,当前使用 Kimi K2.6
OPENAI_API_KEY=<your_openai_compatible_api_key>
OPENAI_BASE_URL=<your_openai_compatible_base_url>
OPENAI_MODEL=kimi-k2.6

# ==================== 搜索工具 ====================
TAVILY_API_KEY=<your_tavily_api_key>

# ==================== 向量数据库 ====================
# Qdrant Cloud(推荐)
QDRANT_URL=<your_qdrant_cloud_url>
QDRANT_API_KEY=<your_qdrant_api_key>

# ==================== 图数据库 ====================
# Neo4j Aura(如使用图记忆)
NEO4J_URI=<your_neo4j_uri>
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your_neo4j_password>

# ==================== Embedding 配置 ====================
# 方案 1:DashScope(推荐,无需本地模型)
EMBED_MODEL_TYPE=dashscope
EMBED_API_KEY=<your_dashscope_key>
EMBED_MODEL_NAME=text-embedding-v3

# 方案 2:本地模型
# EMBED_MODEL_TYPE=local
# EMBED_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2

# ==================== Hugging Face 缓存 ====================
HF_HOME=D:\HF
SENTENCE_TRANSFORMERS_HOME=D:\HF\hub
TRANSFORMERS_CACHE=D:\HF\hub
# 镜像加速(可选,国内有时不稳定)
# HF_ENDPOINT=https://hf-mirror.com
```

> 凭据只允许通过 `.env` 或进程环境变量提供。禁止写入源码、注释、docstring、README、NOTES 或 git 提交。

---

## 2. 教程代码到项目的替换规则

教程代码里使用 GPT/OpenAI 官方模型。本项目统一走 Kimi。替换时不要自行写 `gpt-4o-mini` 之类的 fallback,那会误导实现。

| 教程写法 | 本项目写法 | 说明 |
|---|---|---|
| `model="gpt-4o-mini"` | `model=os.getenv("OPENAI_MODEL")` | 走 Kimi |
| `base_url="https://api.openai.com/v1"` | `base_url=os.getenv("OPENAI_BASE_URL")` | 走 Kimi endpoint |
| `LLM_MODEL_ID` / `LLM_API_KEY` / `LLM_BASE_URL` | `OPENAI_MODEL` / `OPENAI_API_KEY` / `OPENAI_BASE_URL` | 统一项目环境变量命名 |
| `ChatOpenAI(..., temperature=0.7)` | `SimpleChatOpenAI(...)` 或直接 `openai.OpenAI` | 避开 Kimi 不支持的参数 |

### Kimi K2.6 兼容注意

- 不要随意传 `temperature`、`top_p`、`presence_penalty`、`frequency_penalty`。
- 请求体尽量最小:`model + messages`。
- 避免 system-only message,优先把提示作为 `user` 或 `HumanMessage` 发送。
- 不要给 OpenAI 模型 fallback。

---

## 3. 依赖版本记录(现行 vs 历史基线)

同一环境在不同章节学习期间被用户显式改过,以下三组版本分别是不同时间点的真实记录。排查兼容问题时先核对当前解释器实际版本,不要把历史基线直接套到新章节,也不要未经用户授权升级或降级。

### 现行版本(2026-08-25 实测)

Chapter 10 与 Chapter 11 学习阶段的当前环境:

```
hello-agents==0.2.2
fastmcp==2.12.5
mcp==1.16.0
authlib==1.7.2
```

Chapter 11 教程 `00_quick_test.py` 等文件要求 `hello-agents[rl]==0.2.5`,但当前 0.2.2 下 `RLTrainingTool` 触发 ImportError(已实测)。升级需用户明确授权,助手不主动执行。

### Chapter 9 历史基线(2026-07-06)

Chapter 9 学习阶段的 `agent_study` conda 环境基线:

```
hello-agents==0.2.8
websockets==15.0.1
Pillow==12.3.0
protobuf==6.33.6
astor==0.8.1
docstring-parser==0.17.0
psutil==5.9.8
pydantic==2.12.0
tiktoken==0.12.0
```

这是历史快照,不代表当前。回看 Chapter 9 代码时应以它为准。

---

## 4. Anaconda 路径迁移

Anaconda 安装目录已从 `D:\Anaconda` 迁移为 `D:\anaconda3`。所有 conda 解释器路径以 `D:\anaconda3\envs\agent_study\python.exe` 为准。旧章节或旧笔记中出现的 `D:\Anaconda\envs\agent_study\python.exe` 一律失效,统一按新路径替换。

同机另有一个 `llamafactory` conda 环境(含训练栈)。Chapter 11 如需 GPU 训练,可评估复用,但先核验其 torch CUDA 状态。

---

## 5. 已移除的冲突依赖

为消除 Chapter 9 之后环境的依赖冲突,已从 `agent_study` 中移除:

```
gradio
gradio-client
autogen-core
autogen-agentchat
autogen-ext
```

未来如需 AutoGen,按第 9 节的兼容组合恢复,或直接新建独立环境。

---

## 6. 环境自检命令

日常排查先用这两条,基本能覆盖常见依赖问题。

```powershell
# 依赖一致性检查
D:\anaconda3\envs\agent_study\python.exe -m pip check

# 关键包导入检查
D:\anaconda3\envs\agent_study\python.exe -c "import hello_agents, camel, langgraph_sdk, langsmith, pdfplumber, PIL, websockets, google.protobuf, pydantic, tiktoken, qdrant_client, mcp, fastmcp; print('OK')"
```

`fastmcp` 可能出现 `authlib.jose` 弃用警告,这是弃用提示,不是依赖错误。

---

## 7. `load_dotenv()` 必须放在所有 import 之前

### 根因

`hello_agents 0.2.8` 的 `core/database_config.py` 在模块加载时调用了 `load_dotenv()`,并立刻实例化 `db_config = DatabaseConfig.from_env()`。

如果用户脚本的 `load_dotenv()` 放在 `import hello_agents` 之后,框架内部的 `load_dotenv()` 先执行,但它在 site-packages 目录下找不到 `.env`,于是 `db_config` 用空配置初始化。之后用户脚本的 `load_dotenv()` 虽然加载了真正的 `.env`,但 `db_config` 已经固化,不会重新读取。于是 `QDRANT_URL` / `QDRANT_API_KEY` 为空,框架 fallback 到 `localhost:6333`,触发连接失败。

### 正确示例

```python
from dotenv import load_dotenv
load_dotenv()

from hello_agents.tools import MemoryTool
from hello_agents.context import ContextBuilder
# ...
```

### 错误示例

```python
from hello_agents.tools import MemoryTool
from dotenv import load_dotenv
load_dotenv()   # 太晚,框架已经用空配置初始化了
```

### 补充说明

- Qdrant 云连接的 SSL 握手还会受代理节点影响,端口 6333 可能失败。遇到 `[SSL: UNEXPECTED_EOF_WHILE_READING]` 时检查代理节点配置。
- Chapter 8 的 `demo_combined.py` 能正常运行,是因为它碰巧把 `load_dotenv()` 放在了 `hello_agents` 导入之前。
- Chapter 10 的 `03_GitHubMCP.py` 和 `09_A2A_WithAgent.py` 已完成同样的时序适配。

---

## 8. 中文相关性评分绕过与 Windows UTF-8 控制台

### 8.1 中文相关性评分

`ContextBuilder._select()` 用 `content.lower().split()` 做关键词重叠评分。中文没有空格,整句被切成一个 token,与查询词交集近似 0,relevance_score 低于默认 `min_relevance=0.3` 后被全部过滤。

绕过:

```python
ContextConfig(min_relevance=0.0, ...)
```

这是绕过,不是修复。生产化应改用 embedding 相似度。

关键教训:同一坑要处处修。新增 `ContextBuilder` 实例化时,必须把 `min_relevance=0.0` 同步补上。历史上 `ContextAwareAgent` 内部漏过一次,已经补齐。

### 8.2 Windows UTF-8 控制台

`RAGTool.__init__` 曾抛 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2705'`,因为框架用 emoji 输出日志,而 Windows 控制台默认 GBK 编码。异常处理分支里 `print("❌ ...")` 会再次抛同样的异常,掩盖原始错误。

运行前设置:

```powershell
$env:PYTHONIOENCODING="utf-8"
```

所有跑 `hello_agents` 的 PowerShell 会话都建议设置一次。

---

## 9. 可选:恢复 AutoGen

如果只是回看 Chapter 6 的 AutoGen 示例,推荐新建独立环境,例如 `agent_study_autogen`,不要污染 Chapter 9 之后的学习环境。

如果确实需要在 `agent_study` 里恢复 AutoGen,按以下兼容组合安装并重新验证,不要无脑 `pip install autogen-*`:

```powershell
D:\anaconda3\envs\agent_study\python.exe -m pip install `
  "autogen-core==0.7.5" `
  "autogen-agentchat==0.7.5" `
  "autogen-ext==0.7.5" `
  "protobuf==5.29.6" `
  "grpcio-tools>=1.41,<1.72" `
  "tensorboard<2.21"

D:\anaconda3\envs\agent_study\python.exe -m pip check
```

---

## 10. 代理配置(中国大陆用户)

使用 Clash / Clash Verge 时,Qdrant Cloud 端口 6333 和 Neo4j 端口 7687 可能不通。

- 换用普通 Clash 而非 Clash Verge。
- 或切换到香港专线节点。
- 确保 TUN 模式已开启。

---

## 11. 旧章节(qdrant-client 兼容)

如果回看 Chapter 8 并遇到以下报错:

```
ERROR: 'QdrantClient' object has no attribute 'search'
ERROR: 'CollectionInfo' object has no attribute 'vectors_count'
```

那是 `hello-agents 0.2.0` 依赖旧版 qdrant-client API,新版已移除。兼容做法是固定 `qdrant-client==1.11.0`,详见 `chapter08/NOTES.md`。

---

## 12. 快速定位参考

| 现象 | 先看哪一节 |
|---|---|
| 环境变量怎么写、放什么 | 第 1 节 |
| 教程 GPT 代码怎么换成 Kimi | 第 2 节 |
| `hello-agents` 到底是 0.2.2 还是 0.2.8 | 第 3 节 |
| `pip check` 报版本冲突 | 第 3、5、9 节 |
| Anaconda 路径找不到 | 第 4 节 |
| `QDRANT_URL` / `QDRANT_API_KEY` 为空 | 第 7 节 |
| 中文记忆 / RAG 结果被全过滤 | 第 8.1 节 |
| `UnicodeEncodeError: gbk` | 第 8.2 节 |
| 想装 AutoGen | 第 9 节 |
| 6333 / 7687 端口不通 | 第 10 节 |
| Chapter 8 qdrant-client 报错 | 第 11 节 |
