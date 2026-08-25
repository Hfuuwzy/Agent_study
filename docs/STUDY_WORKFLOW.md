# 学习工作流参考

本文档是 Agent_study 项目的权威学习流程参考，面向所有参与者（包括人类和 AI Agent）。

---

## 0. 总原则

1. **学习优先，推送只是记录**。
2. 用户说"学习第 X 章"时，只进入学习准备阶段：生成详细 README、拉取/组合教程代码、辅助用户阅读和实验。
3. 用户说"完成/学完/结束第 X 章"时，才进入完成阶段：生成 NOTES.md、创建章节分支、推送章节分支并给 PR 链接。
4. 不要为了"完成流程"提前生成 NOTES.md 或提前推送。
5. 不要擅自安装依赖、运行安装命令或修改环境；只有用户明确要求安装时才执行安装。
6. 不要擅自扩展功能；用户明确提出扩展时才实现。

**重要说明**：本文件是学习与完成流程的完整权威来源；用户红线与不可重复的教训见项目根目录的 `MEMORY.md`，环境问题见 `ENVIRONMENT.md`。

---

## 1. 学习阶段工作流

当用户说"学习第 X 章"时，按以下步骤执行：

```
用户说"学习第 X 章"
↓
1. 同步本地 main：git checkout main && git pull origin main
2. 读取 Hello-Agents 对应章节教程 Markdown
3. 检查用户是否已有可运行参考文件
4. 生成 chapterX/README.md
   - README 必须详细、重点明确，不要过于简略
   - 需要解释概念、架构、关键代码、学习建议、运行方式
5. 拉取/组合教程 Markdown 中出现的代码片段，生成 chapterX/code/*.py
6. 用户阅读、运行、提问、要求扩展
7. 在用户未说"完成第 X 章"前，不生成 NOTES.md，不推送
```

**核心目标**：让用户掌握本章概念和实现，为后续章节打好基础。

---

## 2. 完成阶段工作流

当用户说"完成/学完/结束第 X 章"时，自动执行以下操作，无需二次确认：

```
用户说"完成/学完/结束第 X 章"
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

**核心目标**：将学习成果以标准格式记录，并推送到远程仓库供后续参考。

---

## 3. Git 工作流硬性规则

- 章节分支的 **PR diff** 必须只包含本章文件（以及明确说明的 MEMORY.md 更新）。
- 不要在本地执行 `git merge chapterX`，用户负责在 GitHub 通过 PR 合并。
- 合并后必须 `git pull --ff-only origin main` 同步本地 main。
- 分支创建前必须确认当前在 main 且已同步远程 main。
- 提交前必须检查：`git diff --staged --stat`。
- 不要把已提取到 main 的未提交章节文件带入其他章节分支。
- 如误推坏分支，删除/重建分支只能使用 `--force-with-lease`，禁止裸 `--force`。
- 每次 git 操作应使用 git-master skill 的规则；尤其避免混合提交、脏工作区提交。

---

## 4. README 内容规范

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

## 5. NOTES 内容规范

NOTES.md 只在用户说"完成/学完/结束第 X 章"之后生成。

必须包含：

1. **核心收获**：本章学到的关键概念。
2. **实践记录**：代码运行结果、遇到的问题。
3. **Bug 修复**：发现的问题及解决方案。
4. **代码对齐差异**：哪些地方与教程一致，哪些地方因为本项目环境做了替换。
5. **深度思考**：个人理解、疑问、反思。
6. **下一步计划**：扩展方向、待验证假设。

---

## 6. 实现前检查清单

在实现每章代码前必须完成：

1. 检查 `chapterX/code/` 中是否已有用户提供的参考文件。
2. 拉取 Hello-Agents 对应章节 Markdown。
3. 深度阅读本章代码实现方式，先判断教程是在"从零构建框架"、还是"基于已有包/已有框架拓展"。
4. 提取所有相关代码片段，包括测试文件、工具文件、示例入口、文档中要求新建的 `.py` 文件。
5. 对照教程结构：目录位置、文件名、类名、函数名、提示词、工具调用、流程顺序。
6. 仅在必要时做本项目环境适配。

---

## 7. 扩展已安装包的详细规则

如果教程章节是在已安装包或已有框架基础上做拓展，例如 Chapter 7 基于已安装的 `hello-agents` 包实现 `MySimpleAgent`、`MyReActAgent`、`MyReflectionAgent`、`MyPlanAndSolveAgent`：

1. 不要把任务理解为"重构整个框架"或"本地重写包源码"。
2. 正确目标是对齐教程片段：继承/调用已有包中的类，只补齐文档要求的新类、新工具、新测试文件。
3. 教程让新建什么 `.py` 文件，就按教程结构创建对应文件；不要把多个实现随意合并到一个文件。
4. 先检查已安装包的真实 API，再做最小兼容适配；兼容适配必须说明原因，例如当前安装包没有 `ToolResponse`，则工具返回 `str`。
5. Demo/test 只负责调用和验证，不应承载核心实现逻辑。
6. 执行下一步前必须先思考：当前章节代码的架构意图是什么？本项目应镜像教程结构，还是只做环境适配？确认后再写代码。

---

## 8. 对齐状态定义

- **已对齐**：基本复制/组合教程代码片段。
- **功能等价**：结构略有差异，但原因明确，例如模型配置替换、Tavily 替代 SerpApi。
- **未对齐**：基于 API 文档自写，需要修复。

---

## 9. 代码拉取与对齐规则

### 9.1 "拉取代码"的定义

用户明确纠正过：**"拉取代码"不是根据 API 文档自己写一套功能等价实现**。

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

---

## 10. 模型配置对齐规则

本项目固定环境变量：

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://kimi.a7m.com.cn/v1
OPENAI_MODEL=kimi-k2.6
TAVILY_API_KEY=...
```

替换规则：

| 教程写法 | 本项目写法 | 说明 |
|---|---|
| `model="gpt-4o-mini"` | `model=os.getenv("OPENAI_MODEL")` | 使用 Kimi 模型 |
| `base_url="https://api.openai.com/v1"` | `base_url=os.getenv("OPENAI_BASE_URL")` | 使用 Kimi endpoint |
| `LLM_MODEL_ID` / `LLM_API_KEY` / `LLM_BASE_URL` | `OPENAI_MODEL` / `OPENAI_API_KEY` / `OPENAI_BASE_URL` | 统一项目环境变量 |
| `ChatOpenAI(..., temperature=0.7)` | `SimpleChatOpenAI(...)` 或直接 `openai.OpenAI` | 避免 Kimi 不支持的参数 |

**Kimi 兼容注意**：

- 对 Kimi K2.6，不要随意传 `temperature`、`top_p`、`presence_penalty`、`frequency_penalty`。
- 请求体尽量保持最小：`model + messages`。
- 避免 system-only message；优先把提示作为 user/HumanMessage 发送。
- 不要给 OpenAI 模型 fallback（如 `gpt-4o-mini`），否则会误导实现。

---

## 11. 安装与环境规则

用户明确要求：

- 环境用户已经安装过，助手不要擅自安装任何东西。
- 不要擅自执行 `pip install`、`conda install`、`npm install` 等安装命令。
- 如果缺依赖，只提供安装指令，等待用户确认或用户自行安装。
- 只有用户明确说"安装/执行安装命令"时，才可以执行安装。

**重要**：具体依赖版本和环境事实记录在 `ENVIRONMENT.md` 中。

---

## 12. Hello-Agents load_dotenv() 时序规则

**重要**：所有使用 `hello_agents` 的脚本，`load_dotenv()` 必须放在所有 import 之前。

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

---

## 13. 中文场景适配

如果教程示例在中文场景下运行，可能遇到以下问题：

### 13.1 中文相关性评分被过滤

**问题**：`hello_agents` ContextBuilder 的 `_select()` 用 `content.lower().split()` 做关键词重叠评分。中文没有空格，整句会被切成一个 token，与查询词的交集≈0，relevance_score≈0，低于默认 `min_relevance=0.3` 全部被过滤。

**解决**：使用 `ContextConfig(min_relevance=0.0)` 绕过过滤。

### 13.2 Windows GBK 编码崩溃

**问题**：`RAGTool.__init__` 抛 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2705'`。

**解决**：运行前 `$env:PYTHONIOENCODING="utf-8"`。所有跑 hello_agents 的 PowerShell 会话都建议设置。

---

## 14. 凭据安全规则

凭据只允许通过环境变量或未纳入版本控制的 `.env` 提供，禁止写入源码、注释、docstring、README、NOTES 或提交消息。

---

## 15. 环境版本事实

### 15.1 Chapter 9 基线环境（2026-07-06）

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

### 15.2 Chapter 10 当前环境（2026-08-25）

```bash
hello-agents==0.2.2
fastmcp==2.12.5
mcp==1.16.0
authlib==1.7.2
```

**重要**：这两组版本分别是不同时间点的真实环境记录。后续排查兼容问题时必须先核对当前解释器中的实际版本，不能把 Chapter 9 的 `0.2.8` 历史基线直接套用到新章节，也不要未经用户授权主动升级或降级。

### 15.3 Anaconda 路径迁移

2026-08-25 补充：Anaconda 安装目录已从 `D:\Anaconda` 迁移为 `D:\anaconda3`。本文件及旧章节记录中所有 `D:\Anaconda\envs\agent_study\python.exe` 路径一律以 `D:\anaconda3\envs\agent_study\python.exe` 为准。

---

## 16. AutoGen 兼容组合（如需恢复）

如果只为回看 Chapter 6 的 AutoGen 示例，推荐新建独立环境，例如 `agent_study_autogen`，避免再次污染 Chapter 9+ 的学习环境。如需在现有环境恢复，可使用以下兼容组合：

```bash
D:\anaconda3\envs\agent_study\python.exe -m pip install \
  "autogen-core==0.7.5" \
  "autogen-agentchat==0.7.5" \
  "autogen-ext==0.7.5" \
  "protobuf==5.29.6" \
  "grpcio-tools>=1.41,<1.72" \
  "tensorboard<2.21"

D:\anaconda3\envs\agent_study\python.exe -m pip check
```

---

## 17. 学习建议

1. **按顺序学习**：每章都建立在前一章基础上。
2. **动手实践**：不要只看，要跑代码、改代码。
3. **记录笔记**：每章学完更新 `NOTES.md`。
4. **遇到问题**：先查 `ENVIRONMENT.md` 的「快速定位参考」，再按现象定位。
5. **扩展实验**：尝试修改参数、添加新功能。

---

**最后更新**：2026-08-25

**相关文档**：
- 项目规则与教训：`../MEMORY.md`
- 环境配置与故障排查：`ENVIRONMENT.md`
- 项目说明与章节进度：`../README.md`
