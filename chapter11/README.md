# 第十一章 Agentic-RL（智能体强化学习训练）

> [!info] 学习概览
> **目标**: 理解从 LLM 训练到 Agentic RL 的完整演进，掌握 SFT（监督微调）与 GRPO（群组相对策略优化）两大训练方法的原理与实践
> **实践**: 通过 HelloAgents 框架新引入的 `RLTrainingTool` 统一工具，加载 GSM8K 数据集、设计奖励函数、进行 LoRA 参数高效微调、评估模型、跑通端到端训练 pipeline
> **重点**: LLM 训练全景图（预训练 / SFT / 奖励建模 / RLHF）、Agentic RL 六大核心能力、LoRA 低秩适配原理、GRPO 组内相对奖励、HelloAgents 四层训练架构、RLTrainingTool 的四种 action

---

## 1. 本章定位

本章解决什么问题，需要先看清它与前十章的区别。到第十章为止，我们一直在**使用**现成的 LLM：给它设计提示词（第三、四章）、封装工具系统（第六、七章）、接入记忆与 RAG（第八章）、优化上下文（第九章）、连接通信协议（第十章）。在这些章节里，模型本身对我们来说是一个固定的黑盒推理引擎，我们优化的是模型外面的壳。

但在复杂任务面前，提示和框架的优化是有上限的。教程在 11.1 节提出了三个问题：

1. **如何让智能体具备更强的推理能力？** -- 仅仅靠"请逐步思考"这类提示，模型很难学会训练数据之外更优的推理策略。
2. **如何让智能体学会更好地使用工具？** -- 模型能调用工具，但"何时该用、用哪个、怎么组合"无法靠提示一条条指定。
3. **如何让智能体能够自我改进？** -- 输出质量固定，模型不会因为"这次答错了"而变得更好。

答案就是 **Agentic RL（基于强化学习的智能体训练）**：把 LLM 当作一个**可学习的策略（policy）**，嵌入智能体的感知-决策-执行循环，通过强化学习优化**多步任务**的累积表现。本章为 HelloAgents 框架引入强化学习训练能力，技术选型如下：

| 维度 | 选择 | 原因（教程原文依据） |
|------|------|----------------------|
| 强化学习框架 | **TRL**（Hugging Face） | 成熟稳定、功能完整、易于集成（11.1.4） |
| 基础模型 | **Qwen3-0.6B** | 0.6B 参数适合普通 GPU 训练、性能优秀、开源免费（11.1.4） |
| 训练算法 | **SFT + GRPO** | SFT 学任务格式与基线能力，GRPO 通过强化学习优化推理策略 |
| 数据集 | **GSM8K**（小学数学应用题） | 有明确答案可自动评估、天然需要 2-8 步多步推理（11.2.1） |

一句话概括本章地位：**前九章教我们"怎样用好一个模型"，本章教我们"怎样训练出一个更会推理、会用工具、能自我改进的模型"。**

---

## 2. 核心概念

### 2.1 从强化学习到 Agentic RL

教程在 11.1.1 节用一个数学问题把强化学习框架映射到 LLM 智能体（Janet 每天卖鸭蛋的收入问题：`16 - 3 - 4 = 9`，`9 × 2 = 18`）：

| 强化学习要素 | 在数学求解智能体中的对应 |
|--------------|--------------------------|
| **智能体** | 基于 LLM 的推理系统 |
| **环境** | 数学问题和验证系统 |
| **状态** | 当前问题描述 + 已有推理步骤 |
| **行动** | 生成下一步推理或最终答案 |
| **奖励** | 答案是否正确（正确 +1，错误 0） |

教程对比了传统监督学习的三点局限：一是**数据质量决定上限**，模型只能模仿训练数据、难以超越；二是**缺乏探索能力**，只能被动学习人类给出的路径；三是**难以优化长期目标**，无法精确优化多步推理的中间过程。强化学习则让智能体自主生成多个候选答案、按正确性获得奖励，从而发现比人类标注更好的解题方法。这就是 Agentic RL 的核心：**将 LLM 作为可学习策略，通过试错优化多步任务表现**。

### 2.2 LLM 训练全景图

一个强大的 LLM 的诞生通常经历两大阶段（教程图 11.1）：

**预训练（Pretraining）**：目标是从数 TB 级文本中学习语言规律和世界知识，使用自监督的因果语言建模（下一个词预测）：

$$
\mathcal{L}_{\text{pretrain}} = -\sum_{t=1}^{T} \log P(x_t | x_1, x_2, ..., x_{t-1}; \theta)
$$

**后训练（Post-training）**：解决预训练模型"只会预测下一个词、不会听指令"的问题，通常包含三步：

1. **监督微调（SFT）**：用 `(prompt, completion)` 对学习任务格式与基本能力，数据量小、人工标注、快速见效。
2. **奖励建模（RM）**：用偏好对比数据 `(chosen, rejected)` 训练奖励模型，给更好的回答更高的分。
3. **强化学习微调（RL）**：以奖励模型为信号优化策略，最经典的是 PPO：`J = E[r_phi(x,y)] - beta * D_KL(pi_theta || pi_ref)`，即最大化奖励同时用 KL 散度约束模型不要偏离参考策略太远。

传统 RLHF 依赖大量人工标注的偏好数据，成本高昂；RLAIF 用强大的 AI 模型（如 GPT-4）替代人类标注员，效果接近甚至超过 RLHF 而成本大幅降低（11.1.2）。

### 2.3 Agentic RL 的核心理念（PBRFT vs Agentic RL）

强化学习用马尔可夫决策过程（MDP）五元组 `(S, A, P, R, γ)` 形式化。教程 11.1.3 把传统后训练（称为 **PBRFT**：Preference-Based Reinforcement Fine-Tuning）与 **Agentic RL** 放到 MDP 框架下对比（表 11.1）：

| MDP 维度 | PBRFT（传统对话优化） | Agentic RL |
|----------|------------------------|------------|
| **状态** | `s_0 = prompt`，单步，不变化 | `s_t = (prompt, o_1, ..., o_t)`，多步，随行动演化 |
| **行动** | 只有文本生成 | 文本生成 + 工具调用 + 环境操作 |
| **转移** | 无状态转移 | `s_{t+1} ~ P(s_{t+1}|s_t, a_t)`，行动改变环境状态 |
| **奖励** | 单步奖励，任务结束才给 | 多步奖励，可中途给予部分奖励（稀疏/密集/混合） |
| **目标** | 最大化单步期望奖励 | 最大化累积折扣奖励 `E[ Σ γ^t r(s_t, a_t) ]` |

教程用了一个例子说明区别：PBRFT 场景下用户问"请解释什么是强化学习"，模型生成完整回答直接给分；Agentic RL 场景下用户让"帮我分析 GitHub 仓库代码质量"，智能体要先调 GitHub API（+0.1）、读代码文件（+0.1）、分析质量（+0.2）、生成报告（+0.6），总奖励 1.0 是各步累积。**多步交互、状态随行动演化、每一步都有反馈**，这是 Agentic RL 的关键特征，也是它让 LLM 从"对话助手"进化为"自主智能体"的根本转变。

Agentic RL 要赋予智能体六大核心能力（教程图 11.2）：**推理（Reasoning）**、**工具使用（Tool Use）**、**记忆（Memory）**、**规划（Planning）**、**自我改进（Self-Improvement）**、**感知（Perception）**。

### 2.4 HelloAgents 的四层训练架构与 RLTrainingTool

教程 11.1.4 给出了 HelloAgents 的 Agentic RL 四层架构（图 11.3）：

| 层 | 包含组件 | 职责 |
|----|----------|------|
| **数据集层** | `GSM8KDataset`、`create_sft_dataset()`、`create_rl_dataset()` | 数据加载与格式转换 |
| **奖励函数层** | `MathRewardFunction` 基类、`AccuracyReward`、`LengthPenaltyReward`、`StepReward`、`create_*_reward()` | 定义什么是好的行为 |
| **训练器层** | `SFTTrainerWrapper`、`GRPOTrainerWrapper` | 具体训练逻辑 + LoRA 支持 |
| **统一接口层** | `RLTrainingTool` | 对上层暴露统一训练工具 |

统一接口层是本框架设计的**核心抽象**：用户不需要关心 TRL、Peft 等底层库的细节，只需要向 `RLTrainingTool.run()` 传入一个配置字典：

| action | 作用 |
|--------|------|
| `"train"` | 训练模型（`algorithm` 指定 `sft` 或 `grpo`） |
| `"load_dataset"` | 加载数据集（`format` 指定 `sft` 或 `rl`） |
| `"create_reward"` | 创建奖励函数（`reward_type` 指定类型） |
| `"evaluate"` | 评估模型（返回准确率、平均奖励等） |

---

## 3. 架构与目录结构

### 3.1 教程模块结构

```
hello_agents/                        # HelloAgents 框架（0.2.5 的 [rl] extra）
├── rl/                              # 第十一章新增的 Agentic RL 模块
│   ├── datasets.py                  # 数据集层：GSM8KDataset / create_sft_dataset / create_rl_dataset
│   ├── rewards.py                   # 奖励函数层：MathRewardFunction / AccuracyReward / LengthPenaltyReward / StepReward
│   ├── sft_trainer.py               # 训练器层：SFTTrainerWrapper（LoRA 支持）
│   ├── grpo_trainer.py              # 训练器层：GRPOTrainerWrapper（LoRA 支持）
│   └── ...                          # format_math_dataset 等格式转换工具
└── tools/
    └── rl_training_tool.py          # 统一接口层：RLTrainingTool（四种 action）
```

> 说明：以上模块路径来自教程 11.1.4 的四层架构描述，用于理解设计意图。本项目的实际代码文件（`chapter11/code/`）全部通过 `RLTrainingTool` 这一统一入口使用框架，不需要直接接触底层类。

### 3.2 本章代码文件清单

以下代码文件来自 HelloAgents 教程第十一章（已**逐字下载**到 `chapter11/code/`）：

| 文件名 | 内容 | 阅读优先级 |
|--------|------|------------|
| `00_quick_test.py` | 快速冒烟测试：数据加载 + SFT + GRPO + 奖励函数（**会真实触发训练**） | 第 4 个阅读 |
| `01_dataset_loading.py` | 数据集加载与 SFT/RL 格式对比（仅打印配置） | 第 1 个阅读 |
| `02_reward_functions.py` | 三种奖励函数创建与 `MathRewardFunction` 测试（仅打印配置） | 第 2 个阅读 |
| `03_lora_configuration.py` | LoRA 配置与参数调优建议（仅打印配置） | 第 3 个阅读 |
| `04_sft_training.py` | SFT 训练完整流程（6 个配置示例，训练调用已注释） | 第 5 个阅读 |
| `05_grpo_training.py` | GRPO 训练完整流程（6 个配置示例，训练调用已注释） | 第 6 个阅读 |
| `06_complete_pipeline.py` | `AgenticRLPipeline` 端到端 pipeline（**会真实触发训练并覆盖 config.json**） | 第 8 个阅读 |
| `07_model_evaluation.py` | 基线/SFT/GRPO 三模型评估（仅打印配置） | 第 7 个阅读 |
| `08_distributed_training.py` | 分布式训练示例（`accelerate launch` 启动，**会真实触发训练**） | 第 9 个阅读 |
| `config.json` | pipeline 的配置文件（`base_model`、`sft`、`grpo`、`eval`、`monitoring`） | 配合 06 阅读 |
| `.env.example` | 环境变量模板（`LLM_*` 系列 + `RL_*` 系列 + HF 镜像配置） | 配合运行前阅读 |
| `accelerate_configs/` | 分布式训练配置（`multi_gpu_ddp.yaml`、`deepspeed_zero2.yaml`、`deepspeed_zero3.yaml` + README） | 配合 08 阅读 |

---

## 4. 关键代码讲解

> 重点：不只贴代码，讲清楚"**为什么这么写**"。

### 4.1 统一入口 RLTrainingTool（00_quick_test.py）

```python
from hello_agents.tools import RLTrainingTool

tool = RLTrainingTool()
result = tool.run({
    "action": "load_dataset",
    "format_type": "sft",          # ⚠️ 注意：教程正文用 "format"，本文件用 "format_type"
    "split": "train",
    "max_samples": 5
})
data = json.loads(result)
```

**设计意图**：

- 所有操作（数据/训练/奖励/评估）统一走 `run(config_dict)`，返回 **JSON 字符串**，调用方用 `json.loads()` 解析。这样设计的好处是：配置可序列化、可放进配置文件（06 就是这么做的）、可被外部工具（如 wandb / 分布式调度）传递。
- 你不需要先学 TRL 的 `SFTTrainer`、`GRPOTrainer` 的完整 API，只要会组装配置字典，这是这章"不专注于构造工具而是学会应用"的设计初衷（11.1.5）。
- `max_samples` 是控制实验规模的**第一杠杆**：快速测试用 10-100 个样本，完整训练用 `None`（全部 7473 个样本）。教程特别提醒：快速示例跑完准确率很低是正常的，因为模型只见过 0.7% 的训练样本且只跑了一轮。

**为什么 00 用 `format_type` 而教程正文用 `format`**：代码文件与教程 Markdown 存在版本偏差。1、6 号文件都用 `format`（与教程一致），只有 00 用 `format_type`。运行时若报参数错误，优先按教程正文的 `"format": "sft"` 修改。这是"代码与教程不一致"的第一处，详见第 6.3 节。

### 4.2 数据集加载（01_dataset_loading.py）

```python
config = {
    "action": "load_dataset",
    "format": "rl",                 # 或 "sft"
    "split": "train",               # 或 "test"（GSM8K 测试集 1319 个样本）
    "max_samples": 5,
    "model_name": "Qwen/Qwen3-0.6B" # RL 格式需要模型名来套用对话模板
}
```

**为什么 RL 格式不包含完整解答**：两种训练格式的数据形态截然不同（11.2.1）：

| 格式 | 字段 | 设计意图 |
|------|------|----------|
| **SFT** | `prompt` + `completion`（可选 `text`） | completion 给出完整解题过程，模型直接"模仿"标准答案 |
| **RL** | `question` + `prompt` + `ground_truth` + `full_answer` | 只给最终答案，**推理过程要模型自己生成**，奖励函数再评判 |

`prompt` 使用模型对话模板（Qwen 的 `<|im_start|>` 标记），把问题包成 user 消息、留出 assistant 回复位置；`ground_truth` 只有最终答案（如 `"72"`），用于计算奖励。这种设计的核心思想是：**强迫模型自主推理，而不是记忆答案** —— 这正是从 SFT（模仿）迈向 RL（试错优化）的前提。

### 4.3 奖励函数（02_reward_functions.py）

```python
from hello_agents.rl import MathRewardFunction

reward_fn = MathRewardFunction(tolerance=1e-4)
rewards = reward_fn(completions=["...2+2=4. Final Answer: 4"], ground_truth=["4"])
answer = reward_fn.extract_answer(text)     # 从生成文本中提取数字答案
reward_fn.compare_answers(pred, truth)      # 带容差的答案比较
```

**三种内置奖励**（教程 11.2.2，公式原文）：

| 奖励 | 公式 | 设计意图 |
|------|------|----------|
| **准确率奖励** `AccuracyReward` | 答案正确 1，错误 0 | 最基础，简单直接；缺点是稀疏，无法区分"接近正确" |
| **长度惩罚** `LengthPenaltyReward` | `r_acc - α·max(0, l - l_target)` | 鼓励简洁、控制推理成本（更短输出 = 更少 token） |
| **步骤奖励** `StepReward` | `r_acc + β·s` | 鼓励清晰推理步骤、提高可解释性 |

**为什么惩罚只在答案正确时生效**：长度惩罚和步骤奖励都以准确率为基底（先 `r_acc` 再叠加），防止模型为了拿步骤奖励生成一堆废话、或者为了躲长度惩罚故意答错。教程特别强调可以组合：准确率+长度惩罚适合对话/问答，准确率+步骤奖励适合教育/可解释 AI，三者并用需要小心调整 `α` 和 `β` 防止某个目标过度主导。

奖励函数的统一签名是 `reward_fn(completions: List[str], **kwargs) -> List[float]`，`kwargs` 里带 `ground_truth`。**逐样本返回奖励列表**而不是单个数值，是为了和 GRPO 按组计算相对奖励对齐（见 4.6）。自定义奖励函数也只要遵循同一签名（11.2.3），例如教程的 `tolerant_reward` 按误差分档给分（完全正确 1.0 / 接近 0.5 / 错误 0），并用 `register_reward_function("my_dataset", fn)` 注册，训练时 `dataset="my_dataset"` 会自动匹配同名奖励函数。

### 4.4 LoRA 参数配置（03_lora_configuration.py）

```python
config = {
    "use_lora": True,
    "lora_r": 16,       # LoRA 秩（教程正文写作 lora_rank，见 6.3 差异）
    "lora_alpha": 32,   # 缩放因子，通常 = 2 × r
}
```

**为什么 LoRA 可行**：教程 11.3.2 给出原理。微调时的权重变化可以写成低秩分解 `ΔW = BA`，其中 `B ∈ R^(d×r)`、`A ∈ R^(r×k)`、`r << min(d,k)`。前向传播变成 `h = Wx + BAx`，原权重 `W` 冻结，只训练 `B` 和 `A`。以 4096×4096 的矩阵、r=8 为例：全量参数 16,777,216，LoRA 参数 `8×(4096+4096)=65,536`，**参数减少 256 倍**。教程给出的显存参考：Qwen3-0.6B 全量微调约需 12GB（FP16）/ 24GB（FP32），LoRA 微调只需约 4GB（代码 03 的注释）。

**为什么 lora_alpha 通常是 r 的 2 倍**：实际更新是 `ΔW = (α/r)·BA`，`α` 控制 LoRA 对模型的影响强度。秩 `r` 决定表达能力（4-8 适合小任务，16-32 适合复杂任务），`α` 与 `r` 一起调节缩放，社区惯例 `α = 2r`。

### 4.5 SFT 训练（04_sft_training.py）

这个文件给出了 6 个配置示例，按复杂度递增，理解其**分层设计意图**是重点：

| 示例 | 关键参数 | 设计意图 |
|------|----------|----------|
| 1. 最简 | `max_samples=10, num_epochs=1` | 只验证流程能跑通 |
| 2. 标准 | `1000 样本, 3 epochs, lr=5e-5, lora_r=16` | 推荐的平衡配置 |
| 3. 全量 | `max_samples=None`（全部 7473 样本） | 追求效果 |
| 4. 学习率对比 | 1e-5 / 5e-5 / 1e-4 | 学习率是"保守/推荐/激进"三档 |
| 5. 显存优化 | `batch_size=1, lora_r=8` | 显存受限时的兜底方案（代码注释预计 ~3-4GB） |
| 6. 实战 | `100 样本, 1 epoch, lora_r=16` | 最快能出结果的组合 |

**为什么需要 SFT**（11.3.1 的对比实验）：预训练模型面对数学问题只会输出"也许我该用一个计算器……"这类冗长无结构的话，没有明确的最终答案，**无法提取答案、无法评估、无法给奖励**。SFT 模型则会输出 `Step 1: ... / Step 2: ... / Final Answer: 72` 的结构化格式。所以 SFT 是 RL 的**前提**：它教会模型输出格式、推理模式，建立基线，缩小 RL 的探索空间。没有 SFT 直接做 RL 几乎必然失败（教程原文）。

训练中的监控要点（11.3.3）：**损失**应持续下降；**梯度范数**应在 0.1-10 之间（>100 梯度爆炸、<0.01 梯度消失）；**学习率**按 warmup 策略先升后降。配套参数建议：`batch_size` 按显存选（4GB 用 1-2，8GB 用 4-8，16GB 用 8-16）、`optimizer="adamw"`、`weight_decay=0.01`、`warmup_ratio=0.1`。教程给出的完整配置针对 8GB 显存 GPU、预计 30-60 分钟。

### 4.6 GRPO 训练（05_grpo_training.py）

```python
config = {
    "action": "train",
    "algorithm": "grpo",
    "model_name": "./output/sft_standard",  # 或基础模型名
    "batch_size": 2,
    "learning_rate": 1e-5,   # 比 SFT 小 10 倍！
    "use_lora": True,
}
```

**为什么 GRPO 而不是 PPO**（11.4.1）：PPO 在 LLM 训练中需要训练 **Value Model** 来估计优势函数 `A(s,a) = Q(s,a) - V(s)`，因此要同时维护四个模型（Policy / Reference / Value / Reward），工程复杂、显存占用高、训练不稳定。GRPO 的核心简化是：**去掉 Value Model，用组内相对奖励代替绝对优势函数**：

$$
J_{\text{GRPO}}(\theta) = \mathbb{E}\left[ \frac{\pi_\theta}{\pi_{\text{ref}}} \cdot (r(s,a) - \bar{r}_{\text{group}}) \right] - \beta \cdot D_{KL}(\pi_\theta || \pi_{\text{ref}})
$$

训练循环（11.4.3）：对每个问题用当前策略生成 `num_generations` 个答案（构成一组）→ 逐个算奖励 → 减去组内平均得到相对奖励 `r_i - r̄` → 按相对奖励更新策略（同时加 KL 惩罚防偏离）。

用教程的例子看组内相对奖励：4 个答案的奖励为 `[1.0, 1.0, 0.0, 0.8]`，组平均 `0.7`，相对奖励 `[0.3, 0.3, -0.7, 0.1]`。正确且简洁的答案正向激励，错误答案负向惩罚，冗长但正确的奖励被稀释。**这鼓励模型生成"比平均更好"的答案，而不是盲目追求绝对高分，从而显著降低奖励方差**。

**为什么 GRPO 学习率必须小**：GRPO 是在 SFT 基线上继续优化，学率太高会让模型"忘了"SFT 学到的格式。教程 11.4.2 明确：学习率建议 1e-6 ~ 1e-5，**在小模型上 5e-5 可能导致策略坍塌（准确率大幅下降）**；代码 05 的注释进一步提示"必要时可调至 1e-6"。GRPO 显存占用比 SFT 高（要同时生成多个答案 + 存参考模型输出），所以 `batch_size=2`，且 `batch_size` 必须能被 `num_generations` 整除（11.1.5 快速示例默认 `num_generations=8`）。监控的三个核心指标：平均奖励（应上升）、KL 散度（应保持在 0.01-0.1）、准确率（应提升）。监控工具三种：wandb（推荐，自动记录 train/reward、train/kl、train/loss 等）、TensorBoard（`tensorboard --logdir=...` 后访问 :6006）、纯日志。

### 4.7 端到端 pipeline（06_complete_pipeline.py）

```python
class AgenticRLPipeline:
    def __init__(self, config_path="config.json"):
        self.rl_tool = RLTrainingTool()
        self.config = self.load_config(config_path)   # JSON 配置外置
        self.results = {}
```

**设计意图**：把整个流程拆成六个有名字的阶段方法（`stage1_prepare_data` → `stage2_sft_training` → `stage3_sft_evaluation` → `stage4_grpo_training` → `stage5_grpo_evaluation` → `stage6_save_results`），每个阶段内部还是只调 `rl_tool.run({...})`。这样做的价值：

- **可插拔**：每阶段是独立方法，想跳过、替换、加日志都很容易。
- **配置外置**：所有超参数放在 `config.json`，训练脚本本身零改动，换参数不用改代码（也方便交给 git 管理 / 对比多组实验）。
- **监控接线**：SFT/GRPO 阶段都把 `use_wandb` / `use_tensorboard` / `wandb_project` 从配置透传给 `run()`，全流程可以被追踪。

**运行注意**：脚本的 `__main__` 会**直接写一份 `config.json`**（覆盖随仓库下载的那份），并把训练结果写入 `training_results.json`。因此最好不要在 `chapter11/code/` 目录里直接跑它，否则自带的 `config.json` 会被覆盖；可以先把它复制到其他工作目录。

### 4.8 模型评估（07_model_evaluation.py）

```python
models = {
    "基线模型": "Qwen/Qwen3-0.6B",        # 原始预训练模型
    "SFT模型": "./output/quick_test/sft",
    "GRPO模型": "./output/quick_test/grpo"
}
```

**为什么评估必须拉上基线**：单看一个模型显示的准确率没有参照系。预期结果满足 `基线 < SFT < GRPO`（教程原文），三个模型一起评估才能证明"SFT 学到了格式、GRPO 又优化了推理"。评估动作返回 `accuracy` / `average_reward` / `num_samples`；教程 11.5.2 还支持 `metrics=["accuracy", "accuracy_at_k", "average_length", "average_steps", "format_correctness"]` + `k=3` 的多指标评估，以及 `return_details=True` 获取每个样本的对错明细做错误分析。错误分析把错误分成**计算错误 / 推理错误 / 理解错误 / 格式错误**四类，还能按真实答案的推理步数分组看"简单/中等/困难"题的准确率落差（教程给出的示例分布：计算错误 42.1%，格式错误只有 5.3%；困难题 5+ 步准确率仅 31.6%）。这些都是**教程输出示例**，不是本机实测数据。

### 4.9 分布式训练（08_distributed_training.py）

```python
world_size = int(os.environ.get("WORLD_SIZE", 1))
local_rank = int(os.environ.get("LOCAL_RANK", 0))
if local_rank == 0:      # 只在主进程打印配置/结果
    ...
result = rl_tool.run(config)   # 训练代码完全不需要修改
```

**设计意图**：分布式训练的写法红利。基于 TRL + HuggingFace Accelerate，训练代码和单 GPU 完全一样，差别只在**启动方式**：`accelerate launch --config_file <配置> ...`。脚本里 `WORLD_SIZE` / `LOCAL_RANK` 由 Accelerate 注入环境变量，脚本用它做两件事：识别当前是否多进程、只在主进程（rank 0）打印日志避免刷屏。配套的三种配置（`accelerate_configs/`）：

| 配置 | 适用场景 | 要点 |
|------|----------|------|
| `multi_gpu_ddp.yaml` | 单机 2-8 卡 | 每 GPU 一份完整模型副本，数据并行，最简最快 |
| `deepspeed_zero2.yaml` | 中等模型（1B-7B） | 优化器状态+梯度分片，约省 30% 显存 |
| `deepspeed_zero3.yaml` | 大模型（>7B） | 完整模型分片 + CPU offload，约省 50% 显存，通信开销大 |

分布式最佳实践（11.6.3）：总 batch = `per_device_batch × num_gpus × grad_accum`，扩卡后学习率按 `lr_new = lr_base × sqrt(total_batch_new / total_batch_base)` 线性缩放。多节点则是改 `num_machines` / `machine_rank` / `main_process_ip`，每个节点启动各自的 `accelerate launch`。

---

## 5. 与前几章的关系

| 章节 | 内容 | 与本章关系 |
|------|------|------------|
| 第二章 | 智能体发展史 | 2.4.2 节已从概念上介绍过强化学习智能体，本章把它落到 LLM 训练上 |
| 第三章 | 大语言模型基础 | 本章的预训练/微调正是第三章 Transformer 知识的应用层 |
| 第四章 | 智能体经典范式 | ReAct 的"推理-行动"循环是"感知-决策-执行"的雏形；SFT/GRPO 训练出的模型正是为了更好的 ReAct |
| 第七章 | 构建 Agent 框架 | `SimpleAgent` / `ReActAgent` / `ToolRegistry` 是训练成果的落地容器 |
| 第八章 | 记忆与检索 | 记忆是 Agentic RL 要优化的六大能力之一（如何决定记住什么、何时更新） |
| 第九章 | 上下文工程 | 上下文优化是"外层工程手段"，RL 是"内层训练手段"，两条提升路径互补 |
| 第十章 | 智能体通信协议 | MCP/A2A 让 Agent 能连工具连其他 Agent，工具使用正是 RL 要训练的行为 |
| **第十一章** | **Agentic-RL** | **当前章节** |

**演进路径**：

```
提示驱动（第3、4章）：写好提示词，模型照做，上限被模型本身锁死
  -> 框架增强（第7-10章）：工具、记忆、上下文、协议，优化模型外面的壳
  -> 训练驱动（第11章）：打开模型这个黑盒，用 SFT + GRPO 把模型本身变强
```

一句话：**前面章节学"怎么指挥一个现成的聪明模型"，本章学"怎么亲手造一个更聪明的模型"**。也是从"工程视角"到"研究视角"的第一次转身。

---

## 6. 本项目实现差异

### 6.1 版本差异（必须如实看待）

| 项目 | 教程要求 | 本机实测（2026-08-25） |
|------|----------|------------------------|
| hello-agents | `"hello-agents[rl]==0.2.5"`（本章专用版本） | **0.2.2**（`pip show hello-agents` 实测） |
| trl | 随 `[rl]` extra 安装 | 1.10.0 ✅ |
| peft | 随 `[rl]` extra 安装 | 0.20.0 ✅ |
| transformers | 随 `[rl]` extra 安装 | 4.57.6 ✅ |
| datasets | 随 `[rl]` extra 安装 | 5.0.1 ✅ |
| accelerate | 随 `[rl]` extra 安装 | 1.14.0 ✅ |
| deepspeed | 分布式可选 | **未安装/未验证**，Windows 上通常不可用 |

**关键事实（实测）**：当前 hello-agents 0.2.2 中 **`RLTrainingTool` 不存在**。`from hello_agents.tools import RLTrainingTool` 在本机会抛 `ImportError`。也就是说，本章所有代码文件目前**都只能阅读、不能运行**，即使环境检查通过。

**为什么不自动升级**：按项目规则（MEMORY.md 第 0 节），不擅自安装依赖、不主动升级版本。升级 `hello-agents[rl]==0.2.5` 必须由你明确授权后再执行。升级后建议立刻验证 `from hello_agents.tools import RLTrainingTool`，因为 0.2.5 是本章专用版本，API 以它为准。

### 6.2 硬件与可行性（诚实评估）

本机硬件环境（已实测）：

```
GPU:       NVIDIA RTX 3060 Laptop, 6144 MiB（6GB）显存
Interpreter: D:\anaconda3\envs\agent_study\python.exe（Python 3.10.20，MEMORY 旧记录的
            D:\Anaconda\envs\agent_study 已失效，Anaconda 目录已迁移为 D:\anaconda3）
torch:     2.12.0+cpu  ->  torch.cuda.is_available() == False（当前只能 CPU 推理/训练）
```

对照教程的显存参考（11.3.3：LoRA 微调小模型约 4GB、4GB 显存只能 batch_size=1-2、8GB 显存才能跑完整配置），诚实结论：

1. **当前状态下，完整 SFT/GRPO 训练不可行**。CPU-only torch 意味着训练速度会慢到没有实用价值，`RLTrainingTool` 内部也会因找不到 CUDA 设备而报错或极慢。
2. 即使装上 CUDA 版 torch，**6GB 显存也只够跑最小化实验**：QLoRA + ≤1.5B 小模型、`batch_size=1`、`max_samples≤100`。0.6B 模型 LoRA 也许勉强可试，但 GRPO（显存需求明显更高）风险很大。
3. 本章实际训练**推荐走云端 GPU**：Google Colab / Kaggle / AutoDL 租卡都行，教程的 8GB 建议本本上跑官方完整配置即可。
4. **分布式章节（11.6.3）定位为"阅读理解为主"**：本机单卡 + CPU + 无 deepspeed，只求读懂 DDP / ZeRO / 多节点的概念与配置文件。

不要因此觉得本章学不了：训练前的**全部知识**（数据集、奖励、LoRA、SFT/GRPO 原理、评估、pipeline 脚手架）都可以在本机静态完成，跑不了的是最后按训练按钮那一下。

### 6.3 代码与教程的差异（逐字下载后实测发现）

| 位置 | 教程正文 | 实际代码文件 | 判断 |
|------|----------|--------------|------|
| 13.lora 参数名 | `lora_rank`（11.3.3、11.6.2） | `lora_r`（00/03/04/05 全部代码） | 版本偏差，运行时以真实 API 为准 |
| load_dataset 参数 | `"format": "sft"` | 00 用 `"format_type": "sft"`；01/06 用 `"format"` | 00 与教程不一致，若报错改回 `format` |
| 训练结果字段 | `result['model_path']`（11.3.3）与 `result['output_dir']`（11.1.5、06 代码）并存 | 06 用 `output_dir` | 教程自身不统一，0.2.5 下需实测 |
| sys.path | 无 | 所有文件头部 `sys.path.insert(0, .../HelloAgents)` | 假设仓库已 clone 到项目根；本机无 `HelloAgents` 目录，实际走 pip 包 |
| 分布式文件名 | 08 的 docstring 与 accelerate_configs/README 里命令行均写 `07_distributed_training.py` | 真实文件是 `08_distributed_training.py` | 运行时把命令中的 `07` 换成 `08` |
| config.json | 自带一份 | 06 脚本 `__main__` 会**覆盖**它并新增 `training_results.json` | 不要在 code/ 目录直接跑 06 |
| `eval.sft_accuracy_threshold` | config 中出现 | pipeline 代码里没有任何一处使用 | 预留字段，未实现阈值判断 |
| 习题的小节引用 | 习题提到 11.2.4 / 11.2.5 / 11.3.3 / 11.4.3 | 正文实际章节是 11.3（SFT）/ 11.4（GRPO）等 | 教程原文如此，属编排瑕疵，不影响学习 |

另外提醒：教程小节编号从 **11.6.4（生产部署）直接跳到 11.8（本章小结）**，没有 11.7。这是教程原貌，不是文件缺页，不要自行补号。

### 6.4 环境约定与网络

- **编码**：照旧在 PowerShell 里先 `$env:PYTHONIOENCODING="utf-8"`，防止 GBK 控制台乱码（脚本大量使用 emoji 和中文）。
- **凭据**：只放环境变量或 `.env`，禁止写进源码/注释/README。本章 `.env.example` 提供了 `LLM_MODEL_ID` / `LLM_API_KEY` / `LLM_BASE_URL` 这套新命名（与项目传统的 `OPENAI_*` 不同），以及 `HF_TOKEN`、镜像配置。
- **模型与数据下载**：本章训练用的是**本地 HuggingFace 模型**（Qwen3-0.6B），不调用 Kimi API；GSM8K 数据集也来自 HuggingFace。国内网络下载这两个都可能失败，方案是代理，或 `$env:HF_ENDPOINT="https://hf-mirror.com"` 走镜像。
- **缺依赖不自动装**：如果升级 0.2.5 后仍缺包，只会提示安装命令，执行需你授权。

---

## 7. 运行方式

### 7.1 环境检查

```powershell
$env:PYTHONIOENCODING="utf-8"

# 检查解释器与核心依赖
& "D:\anaconda3\envs\agent_study\python.exe" -c "import torch; print(torch.__version__, torch.cuda.is_available())"
& "D:\anaconda3\envs\agent_study\python.exe" -c "import hello_agents; print(hello_agents.__version__)"   # 当前 0.2.2
& "D:\anaconda3\envs\agent_study\python.exe" -c "import trl, peft, transformers, datasets, accelerate; print('RL 依赖 OK')"

# 关键检查：本章统一入口是否存在
& "D:\anaconda3\envs\agent_study\python.exe" -c "from hello_agents.tools import RLTrainingTool; print('OK')"
# 预期：0.2.2 下会 ImportError —— 所有脚本当前只能读、不能跑
```

### 7.2 前置条件（重要）

本机 `hello-agents` 是 **0.2.2**，`RLTrainingTool` 不存在（7.1 已实测）。因此本章代码的运行门槛是：**先经你授权升级 `pip install "hello-agents[rl]==0.2.5"`**，并且建议在有 CUDA 的 torch + 8GB+ 显存的环境（云 GPU）运行。在此之前，所有脚本都当**配置示例和阅读材料**用。

### 7.3 只打印配置的安全示例（本机可跑，无需 GPU）

`01_dataset_loading.py`、`02_reward_functions.py`、`03_lora_configuration.py`、`04_sft_training.py`、`05_grpo_training.py`、`07_model_evaluation.py` 这些文件的 `__main__` 只构造配置并打印，**训练/评估调用都被注释**，跑起来没有副作用（但仍受 7.1 的 import 前提约束，即需要先有 `RLTrainingTool` 才能 import）。建议整个代码阅读阶段只在头脑中"运行"它们。

### 7.4 会真实触发的训练类示例（谨慎）

| 脚本 | 触发行为 | 风险提示 |
|------|----------|----------|
| `00_quick_test.py` | 真实下载 Qwen3-0.6B + GSM8K，跑 SFT/GRPO/评估 | 本机 CPU-only 不可行；云端也建议先确认显存 |
| `06_complete_pipeline.py` | 真实训练 + **覆盖 `chapter11/code/config.json`** + 生成 `training_results.json` | 复制到独立工作目录再跑 |
| `08_distributed_training.py` | 真实训练，用 `accelerate launch` 启动 | 本机分布式/DeepSpeed 不可用，仅阅读 |

训练/demo 脚本都没在本机运行过验证（按本项目规则，不运行 `chapter11/code/*.py`）。以上风险来自代码阅读，不是实测结论。

---

## 8. 文件学习路径

建议阅读顺序：**01 → 02 → 03 → 00 → 04 → 05 → 07 → 06 → 08**。逻辑是：先用不触发训练的配置示例把 API 形态学明白，再用 00 看一次"真实冒烟测试长什么样"，接着分头读 SFT/GRPO 两大训练方法，再读评估、最后看整体 pipeline 和分布式。

### 第一阶段：API 与数据（01-03）

| 步骤 | 文件 | 学习重点 |
|------|------|----------|
| 1 | `01_dataset_loading.py` | `load_dataset` 的 `format`/`split`/`max_samples`；SFT 与 RL 格式的字段差异与设计意图 |
| 2 | `02_reward_functions.py` | 三种奖励函数的构造参数；`MathRewardFunction` 的 `extract_answer` / `compare_answers` 测试方法 |
| 3 | `03_lora_configuration.py` | `lora_r`/`lora_alpha` 与 r=8/16/32 三档选择；是否启 LoRA 的取舍 |

### 第二阶段：快速冒烟（00）

| 步骤 | 文件 | 学习重点 |
|------|------|----------|
| 4 | `00_quick_test.py` | 四个 action 串起来跑的完整流程；注意它与教程正文的参数名差异（`format_type` vs `format`） |

### 第三阶段：两大训练方法（04-05）

| 步骤 | 文件 | 学习重点 |
|------|------|----------|
| 5 | `04_sft_training.py` | 从最简到全量的 6 档配置设计；显存优化组合（batch_size=1 + lora_r=8）|
| 6 | `05_grpo_training.py` | GRPO 学习率必须小（1e-5，必要时 1e-6）；SFT→GRPO 的链路写法；batch_size 与 num_generations 整除关系 |

### 第四阶段：评估与整链路（07-06）

| 步骤 | 文件 | 学习重点 |
|------|------|----------|
| 7 | `07_model_evaluation.py` | 基线/SFT/GRPO 三模型对比框架；`use_lora=False` 评估原始模型的写法 |
| 8 | `06_complete_pipeline.py` | `AgenticRLPipeline` 六阶段拆分；config.json 外置配置的工程价值；监控开关的透传 |

### 第五阶段：分布式（08 + accelerate_configs）

| 步骤 | 文件 | 学习重点 |
|------|------|----------|
| 9 | `08_distributed_training.py` | 训练代码零修改、只改启动方式的写法；`WORLD_SIZE`/`LOCAL_RANK` 环境变量 |
| 配套 | `accelerate_configs/` | DDP vs ZeRO-2 vs ZeRO-3 三种 YAML 差异；多节点配置；batch/lr 缩放规则 |

---

## 9. 常见问题

**Q: 为什么我跑所有脚本都报 `ImportError: cannot import name 'RLTrainingTool'`？**
A: 因为本机 hello-agents 还是 0.2.2，`RLTrainingTool` 是 0.2.5 的 `[rl]` 模块（实测确认 0.2.2 的 `hello_agents.tools` 里没有它）。这不是脚本写错，是版本差距。升级需你授权。

**Q: 本机 6GB 显存 + CPU-only torch，能训练吗？**
A: 不能完成有意义的完整训练。详见 6.2：当前状态走"纯阅读"，装好 CUDA 后走"QLoRA + ≤1.5B + 极小样本"实验，真正训练用云 GPU。

**Q: `lora_rank` 和 `lora_r` 到底用哪个？**
A: 教程正文写 `lora_rank`，本章代码文件全部写 `lora_r`。代码是逐字下载的，两者可能是 0.2.5 内部改名的结果。按"代码优先、教程为辅"判断，先按 `lora_r` 用，报参数错误再切换。

**Q: 本章需要配置 Kimi 的 `OPENAI_*` 环境变量吗？**
A: 不需要用于训练。本章模型和数据都来自 HuggingFace 本地加载，不是 API 调用。`.env.example` 里的 `LLM_MODEL_ID` 等是 0.2.5 框架的通用配置命名，在 `RLTrainingTool` 报"缺少 LLM 配置"时才需要关注。

**Q: GRPO 为什么比 SFT 更容易 OOM（显存不足）？**
A: GRPO 要为每个问题同时生成 `num_generations` 个答案并保存参考模型输出（11.4.3）。缓解手段：`num_generations` 8→4、`batch_size` 4→2、`max_new_tokens` 512→256，或开梯度检查点 + 混合精度。

**Q: 为什么教程说 GRPO 学习率 5e-5 会导致"策略坍塌"？**
A: 小模型（0.6B）上学习率偏大时，策略更新一步迈太远，容易丢掉 SFT 学到的输出格式，表现为准确率不升反跌。GRPO 建议 1e-6 ~ 1e-5（11.4.2 原文），`05_grpo_training.py` 注释里也写了这条。

**Q: GSM8K 数据集下载不下来怎么办？**
A: 数据集和 Qwen3-0.6B 模型都在 HuggingFace。开代理，或 `$env:HF_ENDPOINT="https://hf-mirror.com"` 走镜像；也可以预先用 `hf download` 命令缓存到本机。

---

## 10. 学习建议

### 10.1 重点理解

1. **训练三阶段的关系**：预训练给语言能力，SFT 给任务格式，RL 给任务优化。本章的"为什么需要 SFT"对比实验（预训练模型 vs SFT 模型输出）值得反复体会。
2. **PBRFT vs Agentic RL 的本质差异**：单步对话优化 vs 多步序贯决策。这是理解"Agentic"一词的分水岭。
3. **GRPO 为什么省掉 Value Model**：组内相对奖励 `r_i - r̄` 替代优势函数是关键一步。拿到任意一段 GRPO 公式，先找"减号后面是什么"。
4. **奖励函数是 RL 的"宪法"**：准确性/长度/步骤三种奖励如何组合、何时叠加、如何防奖励欺骗（只在正确时给惩罚/奖励）。
5. **统一接口 `RLTrainingTool` 的四层架构**：数据集层→奖励层→训练器层→统一接口层，每一层解决什么问题。
6. **分布式三方案**：DDP（每卡整模型）/ ZeRO-2（优化器+梯度分片）/ ZeRO-3（完整分片+offload），三个 YAML 逐字段对比。

### 10.2 本机分层实践路线

1. **阅读层（现在就能做）**：按第 8 节顺序把 9 个脚本读两遍，重点是把 00/04/05/06 的 config 与教程正文的对应章节对齐，随手在笔记里标出 6.3 节的那些差异点。
2. **升级层（等你授权）**：`pip install "hello-agents[rl]==0.2.5"`，然后只验证一行 `from hello_agents.tools import RLTrainingTool`。这一步不碰训练。
3. **实验层（需要 CUDA 环境）**：装 CUDA 版 torch 后，用 `00_quick_test.py` 的配置但把 `max_samples` 缩到 5-10，模型换成更小的（如 Qwen2.5-0.5B-Instruct），确认流程能转起来。
4. **完整层（云 GPU）**：Colab/Kaggle/AutoDL 按教程标准配置跑一次 `06_complete_pipeline.py`，看 SFT→GRPO→评估三个数（基线/SFT/GRPO 准确率）的爬升。

### 10.3 扩展方向

- 自定义奖励函数：按教程 11.2.3 的 `tolerant_reward` 模板，给"部分正确"的答案按误差分档给分。
- 超参数调优：把 11.6.2 的网格搜索/随机搜索/Optuna 三法各跑一轮（云端），对比调优效率。
- 生产部署 11.6.4 三件套：LoRA 权重合并（`PeftModel.merge_and_unload`）、8-bit 量化推理、FastAPI 服务化。这部分与你后续工作最接轨。
- 思考题：教程末尾 5 道习题中，"智能代码调试助手"的 MDP 映射和"奖励黑客"防御设计都是很好的实战演练素材。

---

## 11. 参考来源

- **教程文档**: `notes/chapter11_tutorial.md`（本项目已拉取的第 11 章 Markdown，2688 行，本章所有内容的唯一权威来源）
- **官方代码**: `chapter11/code/`（逐字下载；教程正文中代码均在 11.1.5 ~ 11.6.4 节）
- **HelloAgents 仓库**: https://github.com/datawhalechina/hello-agents
- 教程 11.8 节后的参考文献（原文列表）中的核心文献：
  - **PPO**: Schulman 等, *Proximal Policy Optimization Algorithms*, 2017（参考文献 [1]）
  - **GRPO 出处（DeepSeekMath）**: Shao 等, *Pushing the Limits of Mathematical Reasoning in Open Language Models*, 2024（参考文献 [2]）
  - **LoRA**: Hu 等, *LoRA: Low-Rank Adaptation of Large Language Models*, 2021（参考文献 [3]）
  - **GSM8K**: Cobbe 等, *Training Verifiers to Solve Math Word Problems*, 2021（参考文献 [4]）
  - **RLHF**: Ouyang 等, *Training language models to follow instructions with human feedback*, 2022（参考文献 [5]）
  - **RLAIF**: Lee 等, *RLAIF: Scaling RLHF with AI Feedback*, 2023（参考文献 [7]）
  - **CoT**: Wei 等, *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models*, 2022（参考文献 [8]）
  - **TRL**: https://github.com/huggingface/trl（参考文献 [9]）
  - **Qwen3**: Qwen Team, *Qwen3 Technical Report*, 2025（参考文献 [10]）
- **HuggingFace 工具链**: [TRL 文档](https://huggingface.co/docs/trl)、[Accelerate 文档](https://huggingface.co/docs/accelerate)、[Peft 文档](https://huggingface.co/docs/peft)

---

**下一步**: 从第 8 节的学习路径开始，先把 `01_dataset_loading.py` 和 `02_reward_functions.py` 与教程 11.2 节逐段对照着读一遍，理解数据集格式和奖励函数的"为什么"。随后决定是否授权升级 `hello-agents[rl]==0.2.5`，再谈任何运行实验。若你想先看真实训练效果，优先准备 Colab/Kaggle/AutoDL 的云 GPU 环境。