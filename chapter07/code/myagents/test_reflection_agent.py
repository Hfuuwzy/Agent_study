"""第 7.4.3 节 MyReflectionAgent 测试脚本。

来源：Chapter 7 文档中的 `test_reflection_agent.py` 代码块；仅调整 import 路径
以适配本地 `chapter07/code/myagents` 包结构。
"""

from importlib import import_module, util

from hello_agents import HelloAgentsLLM
from Agents import MyReflectionAgent


def load_env_if_available() -> None:
    if util.find_spec("dotenv") is None:
        return
    import_module("dotenv").load_dotenv()


load_env_if_available()
llm = HelloAgentsLLM()

# 使用默认通用提示词
general_agent = MyReflectionAgent(name="我的反思助手", llm=llm)

# 使用自定义代码生成提示词（类似第四章）
code_prompts = {
    "initial": "你是Python专家，请编写函数:{task}",
    "reflect": "请审查代码的算法效率:\n任务:{task}\n代码:{content}",
    "refine": "请根据反馈优化代码:\n任务:{task}\n反馈:{feedback}",
}
code_agent = MyReflectionAgent(
    name="我的代码生成助手",
    llm=llm,
    custom_prompts=code_prompts,
)

# 测试使用
result = general_agent.run("写一篇关于人工智能发展历程的简短文章")
print(f"最终结果: {result}")
