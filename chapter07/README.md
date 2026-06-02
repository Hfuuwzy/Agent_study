# Chapter 07 构建你的 Agent 框架

## 当前实现定位

本章代码不再本地重写 `hello_agents/` 包，而是在**已安装的 `hello-agents` 包**基础上，按照教程第 7.4 节给出的代码片段实现四类 Agent 范式扩展。

代码位置：

```text
chapter07/code/myagents/
├── Agents/
│   ├── simple_agent.py       # 7.4.1 MySimpleAgent
│   ├── react_agent.py        # 7.4.2 MyReActAgent
│   ├── reflection_agent.py   # 7.4.3 MyReflectionAgent
│   └── plan_solve_agent.py   # 7.4.4 MyPlanAndSolveAgent
├── tools/
│   ├── calculator.py         # 7.5.1 Tool API 对齐示例
│   ├── search.py
│   └── weather.py
└── demo.py                   # 最小调用演示
```

## 与教程第 7.4 节的对齐关系

| 教程章节 | 本地实现 | 说明 |
|---|---|---|
| 7.4.1 SimpleAgent | `MySimpleAgent` | 继承 `hello_agents.SimpleAgent`，重写 `run`，扩展工具调用、流式响应和工具管理方法 |
| 7.4.2 ReActAgent | `MyReActAgent` | 使用教程中的 `MY_REACT_PROMPT`，按 Thought/Action/Observation 循环执行 |
| 7.4.3 ReflectionAgent | `MyReflectionAgent` | 使用教程中的 `DEFAULT_PROMPTS`，通过 `custom_prompts` 支持定制 |
| 7.4.4 PlanAndSolveAgent | `MyPlanAndSolveAgent` | 使用教程中的 Planner/Executor Prompt，保持 Python 列表计划格式 |
| 7.5.1 Tool 基类 | `tools/*.py` | 对齐当前安装包 API：`Tool.run(parameters) -> str`，不使用 `ToolResponse` |

## 重要兼容说明

当前环境中的 `hello-agents` 安装包 API 与 GitHub main 分支部分代码不同：

- `SimpleAgent(name, llm, system_prompt=None, config=None)` 不接受 `tool_registry` 参数；本地 `MySimpleAgent` 在子类中自行保存工具注册表。
- `ReflectionAgent` / `PlanAndSolveAgent` 不接受 `tool_registry` 参数。
- `Tool.run(self, parameters: dict) -> str`，当前安装包没有 `ToolResponse`。

因此本章代码按**本机已安装包 API**对齐，同时尽量保持第 7.4 节原文片段结构。

## 运行方式

不要在本步骤中重新安装依赖；确认环境已有 `hello-agents` 后运行：

```powershell
cd E:\Code\Agent_study
$env:PYTHONIOENCODING='utf-8'
& "D:/anaconda3/envs/agent_study/python.exe" chapter07/code/myagents/demo.py
```

按教程第 7.4 节测试各 Agent：

```powershell
cd E:\Code\Agent_study\chapter07\code\myagents
$env:PYTHONIOENCODING='utf-8'
& "D:/anaconda3/envs/agent_study/python.exe" test_simple_agent.py
& "D:/anaconda3/envs/agent_study/python.exe" test_react_agent.py
& "D:/anaconda3/envs/agent_study/python.exe" test_reflection_agent.py
& "D:/anaconda3/envs/agent_study/python.exe" test_plan_solve_agent.py
```

其中 `test_simple_agent.py`、`test_reflection_agent.py`、`test_plan_solve_agent.py` 来自原文测试代码块并仅调整本地 import；`test_react_agent.py` 根据原文 ReAct 工具注册与计算问题测试模式整理成独立脚本。

仅做语法验证：

```powershell
cd E:\Code\Agent_study
$env:PYTHONIOENCODING='utf-8'
& "D:/anaconda3/envs/agent_study/python.exe" -m py_compile chapter07/code/myagents/demo.py chapter07/code/myagents/Agents/*.py chapter07/code/myagents/tools/*.py
```

## 参考来源

- 教程第 7 章 Markdown：`docs/chapter7/第七章 构建你的Agent框架.md`
- 本机安装包：`D:\anaconda3\envs\agent_study\lib\site-packages\hello_agents\`
