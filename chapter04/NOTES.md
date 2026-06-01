# Chapter 4 学习笔记

> 智能体经典范式构建：ReAct、Plan-and-Solve、Reflection

---

## 1. 核心收获

### 1.1 三种范式的本质区别

| 范式 | 核心思想 | 适用场景 | 关键特征 |
|------|---------|---------|---------|
| **ReAct** | 边想边做，动态调整 | 探索性任务、工具交互 | Thought → Action → Observation 循环 |
| **Plan-and-Solve** | 先规划后执行 | 结构化任务、数学问题 | Planner + Executor 两阶段 |
| **Reflection** | 执行→反思→优化 | 代码生成、文案创作 | Memory + Reflector + Refiner |

### 1.2 关键实现要点

**ReAct Agent:**
- Action 格式必须严格：`ToolName[input]`
- Finish 需要特殊处理（支持多行内容）
- 工具名称必须用英文（Search/Calculator）

**Plan-and-Solve:**
- Planner 输出必须是可解析的结构（如 Python 列表）
- Executor 需要维护历史上下文
- 适合步骤清晰、可预先规划的任务

**Reflection Agent:**
- Memory 模块是核心，存储执行和反思轨迹
- 反思需要专注于具体维度（如算法效率）
- 迭代终止条件要明确

---

## 2. 实践记录

### 2.1 测试案例

**ReAct Agent - 英伟达GPU查询:**
```
问题: 英伟达最新的GPU型号是什么？
结果: RTX 50系列（5090/5080/5070 Ti/5070）
优化: 自动移除查询中的年份限制，获取最新信息
```

**Plan-and-Solve Agent - 数学应用题:**
```
问题: 水果店三天销售计算
计划: ["计算周二销量", "计算周三销量", "求和三天总量"]
执行: 顺序执行，维护历史结果
```

**Reflection Agent - 斐波那契优化:**
```
初始: O(n) 迭代实现
反思: 指出大数计算的性能瓶颈
优化: 改进类型提示、文档字符串、循环范围
终止: 反思认为已达最优，停止迭代
```

### 2.2 环境配置

- 使用 Tavily API 替代 SerpApi（已有API key，无需额外注册）
- 统一 LLM 客户端 `HelloAgentsLLM`
- 工具模块 `tools.py` 封装搜索和计算器

---

## 3. Bug 修复记录

### 3.1 ReAct Agent

**问题1: Finish 解析失败**
```python
# 修复前
final_answer = re.match(r"Finish\[(.*)\]", action).group(1)
# 问题: 不匹配多行内容

# 修复后
match = re.match(r"Finish\[(.*)\]", action, re.DOTALL)
if match:
    final_answer = match.group(1)
else:
    final_answer = action[6:].strip("[]")  # 降级处理
```

**问题2: Search 查询带年份限制**
```python
# 修复: 自动移除所有年份
import re
query = re.sub(r'\b(20\d{2}|19\d{2})\b', '', query).strip()
```

**问题3: 工具名称解析不支持中文**
```python
# 修复前: re.match(r"(\w+)\[(.*)\]", action_text)
# 修复后: re.match(r"([^[]+)\[(.*)\]", action_text, re.DOTALL)
```

### 3.2 编码问题
```python
# Windows 控制台 GBK 编码问题
# 将 emoji 替换为纯文本
"🧠" → "[思考]"
"✅" → "[成功]"
```

---

## 4. 深度思考

### 4.1 关于 Agent 范式的选择

实际应用中，三种范式并非互斥：
- **ReAct + Reflection**: 动态探索 + 事后优化
- **Plan-and-Solve + Reflection**: 结构化规划 + 质量提升
- 甚至可以三层嵌套：Planner → ReAct Executor → Reflector

### 4.2 Memory 的重要性

Reflection Agent 中的 Memory 模块启示我们：
- Agent 需要"记住"自己的思考过程
- 轨迹（Trajectory）可以用于后续分析和改进
- 短期记忆是长期学习的基础

### 4.3 LLM 能力的边界

测试中发现：
- LLM 会自动添加年份限制（如"2024"），需要显式约束
- 代码生成容易给出次优解，需要 Reflection 机制
- 提示词工程（Prompt Engineering）是核心技能

---

## 5. 代码对齐问题记录

### 5.1 已发现的对齐差异

**Reflection Agent:**
| 方面 | 原仓库 | 我们的实现 | 状态 |
|------|--------|-----------|------|
| Memory 模块 | ✅ 完整实现 | ✅ 已对齐 | 已完成 |
| 提示词设计 | 专业细致（程序员角色） | ✅ 已对齐 | 已完成 |
| 任务类型 | 编程任务（素数/斐波那契） | ✅ 已对齐 | 已完成 |

**Plan-and-Solve Agent:**
| 方面 | 原仓库 | 我们的实现 | 状态 |
|------|--------|-----------|------|
| 提示词详细度 | 详细，带emoji | 较简洁 | 可优化 |
| 错误处理 | 细分异常类型 | 通用 Exception | 可优化 |
| 类型标注 | 有 List[str] 等 | 无 | 可优化 |

**ReAct Agent:**
| 方面 | 原仓库 | 我们的实现 | 状态 | 说明 |
|------|--------|-----------|------|------|
| 工具集成 | SerpApi | Tavily | 不同但等效 | Tavily更稳定 |
| 提示词结构 | 详细 | 简洁 | 功能等效 | 风格差异 |
| 错误处理 | 完善 | 基础 | 可改进 | 非核心差异 |

### 5.2 后续对齐计划

**可选优化（非必需）:**
1. Plan-and-Solve: 添加类型标注和详细错误处理
2. ReAct: 增加重试机制和更完善的日志
3. 统一代码风格（PEP 8、类型提示）

**核心功能已对齐:**
- ✅ 三种范式的核心逻辑完全一致
- ✅ Reflection Agent 的 Memory 模块已完整实现
- ✅ 功能测试通过

---

## 6. 下一步计划

1. **进入 Chapter 5**: 多智能体协作与通信
2. **代码优化**: 根据时间情况选择性对齐提示词细节
3. **扩展实验**: 尝试组合范式（如 Plan-and-Solve + Reflection）

---

## 7. 参考资料

- [Hello-Agents Chapter 4](https://github.com/datawhalechina/hello-agents/blob/main/docs/chapter4/第四章%20智能体经典范式构建.md)
- ReAct 论文: [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- Plan-and-Solve 论文: [Plan-and-Solve Prompting](https://arxiv.org/abs/2305.04091)

---

**完成时间**: 2025-01-20  
**学习时长**: ~4小时
