# 学习流程记忆文档

> 记录与用户的长期约定、流程规则、反思教训。以后所有章节学习都必须优先遵守本文件。

---

## 0. 当前总原则

1. **学习优先，推送只是记录**。
2. 用户说“学习第 X 章”时，只进入学习准备阶段：生成详细 README、拉取/组合教程代码、辅助用户阅读和实验。
3. 用户说“完成/学完/结束第 X 章”时，才进入完成阶段：生成 NOTES.md、创建章节分支、推送章节分支并给 PR 链接。
4. 不要为了“完成流程”提前生成 NOTES.md 或提前推送。
5. 不要擅自安装依赖、运行安装命令或修改环境；只有用户明确要求安装时才执行安装。
6. 不要擅自扩展功能；用户明确提出扩展时才实现。

---

## 1. 标准学习流程

### 1.1 学习阶段（用户说“学习第 X 章”）

```
用户说“学习第 X 章”
↓
1. 同步本地 main：git checkout main && git pull origin main
2. 读取 Hello-Agents 对应章节教程 Markdown
3. 检查用户是否已有可运行参考文件
4. 生成 chapterX/README.md
   - README 必须详细、重点明确，不要过于简略
   - 需要解释概念、架构、关键代码、学习建议、运行方式
5. 拉取/组合教程 Markdown 中出现的代码片段，生成 chapterX/code/*.py
6. 用户阅读、运行、提问、要求扩展
7. 在用户未说“完成第 X 章”前，不生成 NOTES.md，不推送
```

### 1.2 完成阶段（用户说“完成/学完/结束第 X 章”）

用户已确认：**当用户说“完成第 X 章学习”时，自动执行以下操作，无需二次确认**。

```
用户说“完成/学完/结束第 X 章”
↓
1. 生成 chapterX/NOTES.md
   - 核心收获
   - 实践记录
   - Bug 修复记录
   - 代码对齐差异
   - 深度思考
   - 下一步计划
2. 确认只提交本章相关内容
   - 默认只提交 chapterX/
   - 如果本轮确实更新了 MEMORY.md，可一并提交，但必须说明原因
   - 不得把其他章节、临时目录、__pycache__、.opencode 等误提交
3. 创建干净章节分支并推送
   - git checkout main
   - git pull origin main
   - git checkout -b chapterX
   - git add chapterX/ [必要时加 MEMORY.md]
   - git diff --staged --stat  # 必须核验只包含本章内容
   - git commit -m "完成第X章：章节标题"
   - git push -u origin chapterX
4. 报告 PR 链接
   - https://github.com/Hfuuwzy/Agent_study/pull/new/chapterX
5. 用户在 GitHub 创建并合并 PR
6. 用户合并 PR 后，本地同步
   - git checkout main
   - git pull --ff-only origin main
   - git branch -d chapterX
```

### 1.3 Git 工作流硬性规则

- 章节分支的 **PR diff** 必须只包含本章文件（以及明确说明的 MEMORY.md 更新）。
- 不要在本地执行 `git merge chapterX`，用户负责在 GitHub 通过 PR 合并。
- 合并后必须 `git pull --ff-only origin main` 同步本地 main。
- 分支创建前必须确认当前在 main 且已同步远程 main。
- 提交前必须检查：`git diff --staged --stat`。
- 不要把已提取到 main 的未提交章节文件带入其他章节分支。
- 如误推坏分支，删除/重建分支只能使用 `--force-with-lease`，禁止裸 `--force`。
- 每次 git 操作应使用 git-master skill 的规则；尤其避免混合提交、脏工作区提交。

---

## 2. README.md 内容规范

从 Chapter 7 开始，README.md 必须更详细、更有重点，不能只做简略概览。

README 至少包含：

1. **本章定位**：本章解决什么问题，为什么重要。
2. **核心概念**：重要术语和设计思想。
3. **架构图/目录结构**：如果教程有框架结构，必须写清楚模块职责。
4. **关键代码讲解**：不是只贴代码，要解释为什么这么写。
5. **与前几章的关系**：说明如何从已有 ReAct、Reflection、Plan-and-Solve 等内容演进而来。
6. **本项目实现差异**：尤其是模型配置、工具替换、参考代码来源。
7. **运行方式**：命令、环境变量要求、注意事项。
8. **学习建议**：用户阅读时重点关注什么，哪些地方可以扩展实验。

---

## 3. NOTES.md 内容规范

NOTES.md 只在用户说“完成/学完/结束第 X 章”之后生成。

必须包含：

1. **核心收获**：本章学到的关键概念。
2. **实践记录**：代码运行结果、遇到的问题。
3. **Bug 修复**：发现的问题及解决方案。
4. **代码对齐差异**：哪些地方与教程一致，哪些地方因为本项目环境做了替换。
5. **深度思考**：个人理解、疑问、反思。
6. **下一步计划**：扩展方向、待验证假设。

---

## 4. 代码拉取与对齐规则

### 4.1 “拉取代码”的定义

用户明确纠正过：**“拉取代码”不是根据 API 文档自己写一套功能等价实现**。

正确含义：

- 从 Hello-Agents 教程 Markdown 中提取代码片段。
- 如果教程有代码仓库或示例文件，优先拉取示例文件。
- 将教程中的代码片段按原结构组合成可运行实现。
- 如果用户提供了可运行参考文件，优先阅读并使用用户参考文件结构。

错误做法：

- 基于 API 文档自创类、函数、流程。
- 因为环境暂未安装就写 mock 实现。
- 忽略用户提供的可运行参考文件。
- 过度工程化，创建教程没有的包装结构。

### 4.2 实现前检查清单

在实现每章代码前必须完成：

1. 检查 `chapterX/code/` 中是否已有用户提供的参考文件。
2. 拉取 Hello-Agents 对应章节 Markdown。
3. 深度阅读本章代码实现方式，先判断教程是在“从零构建框架”、还是“基于已有包/已有框架拓展”。
4. 提取所有相关代码片段，包括测试文件、工具文件、示例入口、文档中要求新建的 `.py` 文件。
5. 对照教程结构：目录位置、文件名、类名、函数名、提示词、工具调用、流程顺序。
6. 仅在必要时做本项目环境适配。

### 4.2.1 基于已有包拓展时的特殊规则

如果教程章节是在已安装包或已有框架基础上做拓展，例如 Chapter 7 基于已安装的 `hello-agents` 包实现 `MySimpleAgent`、`MyReActAgent`、`MyReflectionAgent`、`MyPlanAndSolveAgent`：

1. 不要把任务理解为“重构整个框架”或“本地重写包源码”。
2. 正确目标是对齐教程片段：继承/调用已有包中的类，只补齐文档要求的新类、新工具、新测试文件。
3. 教程让新建什么 `.py` 文件，就按教程结构创建对应文件；不要把多个实现随意合并到一个文件。
4. 先检查已安装包的真实 API，再做最小兼容适配；兼容适配必须说明原因，例如当前安装包没有 `ToolResponse`，则工具返回 `str`。
5. Demo/test 只负责调用和验证，不应承载核心实现逻辑。
6. 执行下一步前必须先思考：当前章节代码的架构意图是什么？本项目应镜像教程结构，还是只做环境适配？确认后再写代码。

### 4.3 对齐状态标记

- **已对齐**：基本复制/组合教程代码片段。
- **功能等价**：结构略有差异，但原因明确，例如模型配置替换、Tavily 替代 SerpApi。
- **未对齐**：基于 API 文档自写，需要修复。

---

## 5. 模型配置对齐规则

用户已明确：教程中可能使用 GPT/OpenAI 官方模型，但本项目的大模型基础实现应使用 `.env` 中已有 Kimi 配置。

### 5.1 本项目固定环境变量

当前 `.env` 使用：

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://kimi.a7m.com.cn/v1
OPENAI_MODEL=kimi-k2.6
TAVILY_API_KEY=...
```

### 5.2 替换规则

| 教程写法 | 本项目写法 | 说明 |
|---|---|---|
| `model="gpt-4o-mini"` | `model=os.getenv("OPENAI_MODEL")` | 使用 Kimi 模型 |
| `base_url="https://api.openai.com/v1"` | `base_url=os.getenv("OPENAI_BASE_URL")` | 使用 Kimi endpoint |
| `LLM_MODEL_ID` / `LLM_API_KEY` / `LLM_BASE_URL` | `OPENAI_MODEL` / `OPENAI_API_KEY` / `OPENAI_BASE_URL` | 统一项目环境变量 |
| `ChatOpenAI(..., temperature=0.7)` | `SimpleChatOpenAI(...)` 或直接 `openai.OpenAI` | 避免 Kimi 不支持的参数 |

### 5.3 Kimi 兼容注意

- 对 Kimi K2.6，不要随意传 `temperature`、`top_p`、`presence_penalty`、`frequency_penalty`。
- 请求体尽量保持最小：`model + messages`。
- 避免 system-only message；优先把提示作为 user/HumanMessage 发送。
- 不要给 OpenAI 模型 fallback（如 `gpt-4o-mini`），否则会误导实现。

---

## 6. 安装与环境规则

用户明确要求：

- 环境用户已经安装过，助手不要擅自安装任何东西。
- 不要擅自执行 `pip install`、`conda install`、`npm install` 等安装命令。
- 如果缺依赖，只提供安装指令，等待用户确认或用户自行安装。
- 只有用户明确说“安装/执行安装命令”时，才可以执行安装。

### 6.1 Chapter 9 起的新框架环境记录（2026-07-06，2026-08-25 更新）

用户已明确：从 Chapter 9 开始，学习优先按 Hello-Agents 新文档和新框架要求推进；旧章节兼容性不再作为环境约束。若旧章节代码需要回看，可另建环境或按需恢复依赖。

Chapter 9 当时的 `agent_study` conda 环境基线为 **hello-agents 0.2.8 / 新章节优先**：

```bash
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

Chapter 10 在 2026-08-25 使用当前解释器重新核验，实际环境已变为：

```bash
hello-agents==0.2.2
fastmcp==2.12.5
mcp==1.16.0
authlib==1.7.2
```

这两组版本分别是不同时间点的真实环境记录。后续排查兼容问题时必须先核对当前解释器中的实际版本，不能把 Chapter 9 的 `0.2.8` 历史基线直接套用到新章节，也不要未经用户授权主动升级或降级。

为消除依赖冲突，已移除旧冲突源：

```bash
gradio
gradio-client
autogen-core
autogen-agentchat
autogen-ext
```

已验证：

```bash
D:\Anaconda\envs\agent_study\python.exe -m pip check
# No broken requirements found.

D:\Anaconda\envs\agent_study\python.exe -c "import hello_agents, camel, langgraph_sdk, langsmith, pdfplumber, PIL, websockets, google.protobuf, pydantic, tiktoken, qdrant_client, mcp, fastmcp; print('OK')"
```

注意：`fastmcp` 可能出现 `authlib.jose` deprecation warning，这是弃用提示，不是依赖错误。

如果未来需要恢复 AutoGen，可不要直接无脑 `pip install autogen-*`。先使用以下兼容组合并重新验证：

```bash
D:\Anaconda\envs\agent_study\python.exe -m pip install \
  "autogen-core==0.7.5" \
  "autogen-agentchat==0.7.5" \
  "autogen-ext==0.7.5" \
  "protobuf==5.29.6" \
  "grpcio-tools>=1.41,<1.72" \
  "tensorboard<2.21"

D:\Anaconda\envs\agent_study\python.exe -m pip check
```

如果只为回看 Chapter 6 的 AutoGen 示例，推荐新建独立环境，例如 `agent_study_autogen`，避免再次污染 Chapter 9+ 的学习环境。

---

## 7. 章节进度

| 章节 | 主题 | README | 代码 | 学习完成 | NOTES | 推送/合并 |
|---|---|---|---|---|---|---|
| 01 | 初识智能体 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 02 | 智能体发展史 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 03 | 大模型基础 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 04 | Agent 基础范式 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 05 | 低代码平台 | ✅ | 无代码 | ✅ | ✅ | ✅ PR 已合并 |
| 06 | 框架开发实践 | ✅ | ✅ | ✅ | ✅ | ✅ PR 已合并 |
| 07 | 构建你的 Agent 框架 | ✅ | ✅ | ✅ | ✅ | ✅ PR 已合并 |
| 08 | 记忆与检索 | ✅ | ✅ | ✅ | ✅ | ✅ PR 已合并 |
| 09 | 上下文工程 | ✅ | ✅ | ✅ | ✅ | ✅ 已推送 |
| 10 | 智能体通信协议 | ✅ | ✅ | ✅ | ✅ | ✅ 已推送 |

当前状态：Chapter 10 学习完成，NOTES.md 已生成，chapter10 分支已推送，等待用户在 GitHub 创建并合并 PR。

---

## 8. 重要反思记录

### 8.1 Chapter 4 直接推 main 的流程错误

错误：曾经把章节代码直接推送到 main。

正确做法：每章必须独立章节分支，用户通过 GitHub PR 合并。

### 8.2 Chapter 6 CAMEL 代码实现反思

错误：

1. 将“拉取代码”误解为“根据 API 文档自己实现”。
2. 忽略用户提供的 `chapter06/code/camel_ebook.py` 可运行参考文件。
3. 过度工程化，创建了教程没有的复杂包装。
4. 因环境问题倾向写 mock，而用户已说明会自行补装环境。

正确做法：

1. 先检查用户参考文件。
2. 有参考文件就沿用其结构。
3. 无参考文件才拉取教程 Markdown 代码片段。
4. 保持教程原结构，不自创框架。

### 8.3 Chapter 6 LangGraph Kimi 兼容反思

问题：`ChatOpenAI` 和普通 OpenAI 参数导致 Kimi `InvalidParameter`。

修复经验：

- 使用 `SimpleChatOpenAI` 只发送必要字段。
- 不传 `temperature` 等 Kimi K2.6 不支持的采样参数。
- LLM 调用使用 `HumanMessage`，避免 system-only 请求。
- 模型配置从 `.env` 读取，不使用教程 GPT fallback。

### 8.4 Git 分支污染反思

错误：创建章节分支/提交时，工作区已有其他章节文件，导致分支 PR diff 含非本章内容。

正确做法：

- 创建章节分支前必须同步 main。
- 提交前必须 `git diff --staged --stat`。
- 只 `git add chapterX/`，必要时才加 `MEMORY.md`。
- 用户通过 GitHub PR 合并后，本地再 pull。

### 8.5 Chapter 7 workflow 过早推送反思

错误：刚开始 Chapter 7 时，把“生成 NOTES.md 并推送”提前放入 todo。

正确做法：

- 学习阶段只生成 README 和代码。
- NOTES.md 和推送只在用户说“完成第 X 章”后自动执行。
- 学习是核心，推送只是记录。

### 8.6 MEMORY.md 回退事故反思（2026-06-02）

错误：

1. 在排查 Git/分支问题时，把 `MEMORY.md` 从旧 commit 恢复。
2. 我只看到了文件前部 Git 工作流像是更新过，就误判为“正确版本”。
3. 没有核验关键锚点，导致模型配置规则、代码对齐规则、安装规则、反思记录等丢失。

防复发规则：

1. **禁止用旧 commit 覆盖 MEMORY.md**，除非用户明确要求回滚。
2. 编辑 MEMORY.md 前必须先完整读取或至少核验关键章节。
3. 编辑后必须搜索以下锚点：
   - `代码拉取与对齐规则`
   - `模型配置对齐规则`
   - `安装与环境规则`
   - `Git 分支污染反思`
   - `MEMORY.md 回退事故反思`
4. 如果 git 历史里找不到最新记忆，要从会话记录恢复，不要假设旧 commit 正确。
5. 不得只看文件开头就判断 MEMORY 已恢复。

### 8.7 Chapter 7 拓展实现误判反思（2026-06-02）

错误：

1. 一开始把 Chapter 7 的代码任务误判为“本地重写/重构 `hello_agents` 框架”。
2. 没有先完整读懂第 7.4 节的实现意图：它是在已安装 `hello-agents` 包基础上，通过新建 `my_*_agent.py` 等文件进行拓展。
3. 过早自创 `Ext` 包装类和工具返回结构，导致与教程片段和当前安装包 API 都不对齐。

正确做法：

1. 拉取代码前必须先详细阅读本章代码实现方式，判断是“从零构建”还是“基于已有包拓展”。
2. 如果是基于已有包拓展，就跟随教程新建对应 `.py` 文件，保持代码架构性，不要擅自合并或重构。
3. 所有操作都要经过思考：先理解章节架构意图，再提取片段，再最小环境适配。
4. 适配只能解决真实 API 差异，不能变成自创实现；例如安装包 `Tool.run(...) -> str`，就按 `str` 返回适配，而不是引入不存在的 `ToolResponse`。

### 8.8 hello_agents 0.2.8 load_dotenv() 时序问题（2026-07-06）

问题：Chapter 9 的 `ContextBuilder_test.py` 创建 `MemoryTool` 时崩溃，报 `Qdrant连接失败: localhost:6331 拒绝连接`。

根因：`hello_agents 0.2.8` 的 `core/database_config.py` 在模块加载时调用了 `load_dotenv()` 并初始化 `db_config = DatabaseConfig.from_env()`。如果用户脚本的 `load_dotenv()` 放在 `import hello_agents` 之后，框架内部的 `load_dotenv()` 先执行（从 site-packages 目录找 .env，找不到），`db_config` 以空配置初始化。之后用户脚本的 `load_dotenv()` 虽然加载了 .env，但 `db_config` 已经固化，不会重新读取。导致 `QDRANT_URL` / `QDRANT_API_KEY` 为空 → fallback 到 `localhost:6333` → 崩溃。

**修复：所有使用 `hello_agents` 的脚本，`load_dotenv()` 必须放在所有 import 之前。**

```python
# ✅ 正确
from dotenv import load_dotenv
load_dotenv()

from hello_agents.tools import MemoryTool
from hello_agents.context import ContextBuilder
# ...

# ❌ 错误
from hello_agents.tools import MemoryTool
from dotenv import load_dotenv
load_dotenv()  # 太晚，框架已经用空配置初始化了
```

**为什么 Chapter 8 的 demo_combined.py 没问题：** 它的 import 顺序恰好是 `load_dotenv()` 在前，`hello_agents` 在后。

**注意：** Qdrant 云连接还受代理节点影响，端口 6333 的 SSL 握手可能失败。如遇 `[SSL: UNEXPECTED_EOF_WHILE_READING]`，检查代理节点配置。

### 8.9 Chapter 9 中文相关性评分与 GBK 编码问题（2026-08-21）

**问题 1：中文记忆/RAG 结果被 Select 阶段全过滤。**

根因：`hello_agents` ContextBuilder 的 `_select()` 用 `content.lower().split()` 做关键词重叠评分。中文没有空格，整句会被切成一个 token，与查询词的交集≈0，relevance_score≈0，低于默认 `min_relevance=0.3` 全部被过滤。

修复：`ContextConfig(min_relevance=0.0)` 绕过过滤。这是绕过不是修复，生产化应换 embedding 相似度。

**关键教训：同一坑要处处修。** 用户在 `ContextBuilder_test.py` 下半部分新增 `ContextAwareAgent` 时，其内部 `ContextBuilder(config=ContextConfig(max_tokens=4000))` 漏掉了 `min_relevance=0.0`，需要同步补上。修改配置类代码时，必须检查所有实例化点。

**问题 2：Windows GBK 编码崩溃。**

现象：`RAGTool.__init__` 抛 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2705'`。

根因：框架用 `print("✅ ...")` 输出日志，Windows 控制台默认 GBK 编不了 emoji；且异常处理分支里 `print("❌ ...")` 会再次抛同样异常，掩盖原始错误。

修复：运行前 `$env:PYTHONIOENCODING="utf-8"`。所有跑 hello_agents 的 PowerShell 会话都建议设置。

### 8.10 Chapter 10 MCP 运行验证与凭据安全（2026-08-25）

1. `03_GitHubMCP.py` 已完成实际运行验证：成功发现 26 个 GitHub 工具，并返回有效的仓库搜索结果。
2. 程序退出时出现 `unclosed transport` / `Event loop is closed` 告警，但业务结果已完成，且检查时没有残留 `server-github` Node 进程。本次判定为非致命的 asyncio 子进程回收告警；若后续出现进程残留或结果不完整，再排查客户端关闭时序。
3. 其余 Chapter 10 示例只完成代码阅读与 AST 静态验证，不能把静态检查写成运行时验证。当前 23 个 Python 文件全部通过 AST 解析。
4. `03_GitHubMCP.py` 的 docstring 曾含真实 GitHub Token，已替换为 `your_token_here`。源码清理不能使已暴露凭据重新安全，用户仍需在 GitHub 撤销或轮换该 Token。
5. 凭据只允许通过环境变量或未纳入版本控制的 `.env` 提供，禁止写入源码、注释、docstring、README、NOTES 或提交消息。
6. `load_dotenv()` 继续沿用 Chapter 9 的时序规则：必须放在所有 `hello_agents` 导入之前。本章已在 `03_GitHubMCP.py` 和 `09_A2A_WithAgent.py` 中完成该适配。

---

**最后更新**：2026-08-25
