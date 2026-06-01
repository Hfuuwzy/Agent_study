"""
第四章示例代码2: Plan-and-Solve Agent
先规划后执行范式实现
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ast
from llm_client import HelloAgentsLLM

# 规划器提示词
PLANNER_PROMPT_TEMPLATE = """
你是一个顶级的AI规划专家。你的任务是将用户提出的复杂问题分解成一个由多个简单步骤组成的行动计划。
请确保计划中的每个步骤都是一个独立的、可执行的子任务，并且严格按照逻辑顺序排列。
你的输出必须是一个Python列表，其中每个元素都是一个描述子任务的字符串。

问题: {question}

请严格按照以下格式输出你的计划,```python与```作为前后缀是必要的:
```python
["步骤1", "步骤2", "步骤3", ...]
```
"""

# 执行器提示词
EXECUTOR_PROMPT_TEMPLATE = """
你是AI执行专家。请解决当前步骤。

原始问题: {question}

完整计划: {plan}

历史步骤:
{history}

当前步骤: {current_step}

请仅输出该步骤的答案:
"""


class Planner:
    """规划器：生成行动计划"""
    
    def __init__(self, llm: HelloAgentsLLM):
        self.llm = llm
    
    def plan(self, question: str):
        """生成计划"""
        print("--- 生成计划 ---")
        
        prompt = PLANNER_PROMPT_TEMPLATE.format(question=question)
        messages = [{"role": "user", "content": prompt}]
        
        response = self.llm.think(messages)
        print(f"计划: {response}")
        
        # 解析Python列表
        try:
            plan_str = response.split("```python")[1].split("```")[0].strip()
            plan = ast.literal_eval(plan_str)
            return plan if isinstance(plan, list) else []
        except Exception as e:
            print(f"解析计划出错: {e}")
            return []


class Executor:
    """执行器：执行计划步骤"""
    
    def __init__(self, llm: HelloAgentsLLM):
        self.llm = llm
    
    def execute(self, question: str, plan) -> str:
        """执行计划"""
        print("\n--- 执行计划 ---")
        
        history = ""
        
        for i, step in enumerate(plan):
            print(f"\n步骤 {i+1}/{len(plan)}: {step}")
            
            prompt = EXECUTOR_PROMPT_TEMPLATE.format(
                question=question,
                plan=plan,
                history=history if history else "无",
                current_step=step
            )
            
            messages = [{"role": "user", "content": prompt}]
            result = self.llm.think(messages)
            
            print(f"结果: {result}")
            
            # 更新历史
            history += f"步骤 {i+1}: {step}\n结果: {result}\n\n"
        
        return result


class PlanAndSolveAgent:
    """Plan-and-Solve智能体"""
    
    def __init__(self, llm: HelloAgentsLLM):
        self.llm = llm
        self.planner = Planner(llm)
        self.executor = Executor(llm)
    
    def run(self, question: str) -> str:
        """运行完整流程"""
        print(f"问题: {question}")
        print("=" * 50)
        
        # 1. 规划阶段
        plan = self.planner.plan(question)
        
        if not plan:
            return "无法生成计划"
        
        # 2. 执行阶段
        answer = self.executor.execute(question, plan)
        
        print(f"\n最终答案: {answer}")
        return answer


if __name__ == "__main__":
    # 初始化
    llm = HelloAgentsLLM()
    agent = PlanAndSolveAgent(llm)
    
    # 运行示例
    question = "一个水果店周一卖出15个苹果，周二卖出的是周一的2倍，周三比周二少5个。三天总共卖出多少个？"
    agent.run(question)
