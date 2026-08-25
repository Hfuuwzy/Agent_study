# Agent_study 项目入口

> 新会话必读。本项目使用根 `opencode.json` 自动载入完整全局文档；不得只依据本文件的摘要跳过其中任一份。

## 会话启动协议

每次新会话开始时，先完整阅读并以以下文件为准：

1. `MEMORY.md`：用户红线、长期约定和不可重复的教训。
2. `README.md`：项目概览、章节进度的唯一权威来源、各章说明。
3. `docs/STUDY_WORKFLOW.md`：学习/完成阶段、Git、README/NOTES、代码对齐规范。
4. `docs/ENVIRONMENT.md`：环境变量、版本、Kimi 兼容与故障排查。

这些文件通过 `opencode.json` 的 `instructions` 自动注入新会话；若当前工具上下文未包含某一文件，必须先读取完整文件再处理请求。

## 文档职责

| 信息 | 唯一权威来源 |
|---|---|
| 章节进度与当前学习章节 | `README.md` |
| 学习、完成、Git、代码对齐流程 | `docs/STUDY_WORKFLOW.md` |
| 环境配置、依赖版本与排障 | `docs/ENVIRONMENT.md` |
| 用户边界、禁止事项与事故教训 | `MEMORY.md` |

不要把同一事实复制回多个文件；更新时只编辑其权威来源，并在其他文件保留链接或简短指针。

## 章节任务路由

- 开始或完成某章：先读 `docs/STUDY_WORKFLOW.md`，再读 `README.md` 的进度表。
- 编写或修复第 X 章：再读 `chapterX/README.md`、`chapterX/code/` 和已存在的 `chapterX/NOTES.md`；不必在启动时遍历已完成章节。
- 处理环境、模型、依赖或编码问题：先读 `docs/ENVIRONMENT.md`。
- 处理 Git：先读 `docs/STUDY_WORKFLOW.md`，并遵守 `MEMORY.md` 的红线。

## 边界

- 未经用户明确要求，不修改已完成的第 1-10 章内容。
- 不安装依赖、不提前生成 NOTES 或推送、不把凭据写进仓库；完整约束以 `MEMORY.md` 为准。
