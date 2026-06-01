"""
第四章示例代码1: ReAct Agent
Reasoning + Acting 范式实现
"""

import os
import re
import sys

# 添加父目录到路径，以便导入llm_client和tools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_client import HelloAgentsLLM
from tools import ToolExecutor, search

# ReAct 提示词模板
REACT_PROMPT_TEMPLATE = """
你是一个有能力调用外部工具的智能助手。

可用工具如下:
{tools}

请严格按照以下格式进行回应:

Thought: 你的思考过程，用于分析问题、拆解任务和规划下一步行动。
Action: 你决定采取的行动，必须是以下格式之一:
- `Search[搜索内容]`:调用搜索工具查询信息。
- `Calculator[数学表达式]`:调用计算器进行计算。
- `Finish[最终答案]`:当你认为已经获得最终答案时。

重要提示：
1. 工具名称必须使用英文（Search/Calculator），不能使用中文。
2. 搜索时**不要添加年份限制**（如"2024"、"2023"），直接搜索关键词即可。
3. 搜索内容应该简洁，只包含核心关键词。
4. 如果搜索的内容过长，你可以对搜索内容进行一个总结满足要求

现在，请开始解决以下问题:
Question: {question}
History: {history}
"""


class ReActAgent:
    """ReAct智能体"""
    
    def __init__(self, llm: HelloAgentsLLM, tools: ToolExecutor, max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []
    
    def _parse_output(self, text: str):
        """解析Thought和Action"""
        thought_match = re.search(r"Thought:\s*(.*?)(?=\nAction:|$)", text, re.DOTALL)
        action_match = re.search(r"Action:\s*(.*?)$", text, re.DOTALL)
        
        thought = thought_match.group(1).strip() if thought_match else None
        action = action_match.group(1).strip() if action_match else None
        
        return thought, action
    
    def _parse_action(self, action_text: str):
        """解析工具名和输入"""
        # 支持中文工具名和英文工具名
        match = re.match(r"([^\[]+)\[(.*)\]", action_text, re.DOTALL)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return None, None
    
    def run(self, question: str) -> str:
        """运行ReAct循环"""
        print(f"问题: {question}")
        print("=" * 50)
        
        for step in range(self.max_steps):
            print(f"\n--- 步骤 {step + 1} ---")
            
            # 1. 构建提示词
            tools_desc = self.tools.getAvailableTools()
            history_str = "\n".join(self.history)
            
            prompt = REACT_PROMPT_TEMPLATE.format(
                tools=tools_desc,
                question=question,
                history=history_str
            )
            
            # 2. 调用LLM
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.think(messages)
            
            # 3. 解析输出
            thought, action = self._parse_output(response)
            
            if thought:
                print(f"思考: {thought}")
            
            if not action:
                print("警告:未能解析Action")
                break
            
            # 4. 检查是否结束
            if action.startswith("Finish"):
                # 使用re.DOTALL支持多行内容
                match = re.match(r"Finish\[(.*)\]", action, re.DOTALL)
                if match:
                    final_answer = match.group(1)
                    print(f"\n答案: {final_answer}")
                    return final_answer
                else:
                    # 如果格式不匹配，直接返回Finish后的内容
                    final_answer = action[6:].strip("[]")
                    print(f"\n答案: {final_answer}")
                    return final_answer
            
            # 5. 执行工具
            tool_name, tool_input = self._parse_action(action)
            print(f"行动: {tool_name}[{tool_input}]")
            
            observation = self.tools.execute(tool_name, tool_input)
            print(f"观察: {observation}")
            
            # 6. 更新历史
            self.history.append(f"Action: {action}")
            self.history.append(f"Observation: {observation}")
        
        return "达到最大步数限制"


# 示例工具：计算器
def calculator(expression: str) -> str:
    try:
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"计算错误: {str(e)}"


if __name__ == "__main__":
    # 初始化
    llm = HelloAgentsLLM()
    tools = ToolExecutor()
    
    # 注册工具
    search_description = "一个网页搜索引擎。当你需要回答关于时事、事实以及在你的知识库中找不到的信息时，应使用此工具。"
    tools.registerTool("Search", search_description, search)
    tools.registerTool("Calculator", "计算器，用于数学计算", calculator)
    
    print("\n--- 可用的工具 ---")
    print(tools.getAvailableTools())

    # 创建Agent
    agent = ReActAgent(llm, tools, max_steps=5)
    
    # 运行示例
    # question = "英伟达最新的GPU型号是什么？"
    question = "React的实现流程是怎么样的？"
    result = agent.run(question)
    print(f"\n最终结果: {result}")
