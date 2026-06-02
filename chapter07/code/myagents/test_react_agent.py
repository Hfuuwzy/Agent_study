"""第 7.4.2 节 MyReActAgent 测试脚本。

说明：Chapter 7 文档给出 ReAct 实现片段，并说明 ReAct 测试因需要工具而
统一放在文末；当前缓存文档未出现独立 `test_react_agent.py` 代码块。本文件按
文档中的 ReAct 工具注册与计算问题模式整理为独立测试脚本。
"""

from importlib import import_module, util

from hello_agents import HelloAgentsLLM
from Agents import MyReActAgent
from tools import CalculatorTool, SearchTool, WeatherTool

ToolRegistry = import_module("hello_agents.tools.registry").ToolRegistry


def load_env_if_available() -> None:
    if util.find_spec("dotenv") is None:
        return
    import_module("dotenv").load_dotenv()


# 加载环境变量
load_env_if_available()

# 创建LLM实例
llm = HelloAgentsLLM()

# 注册工具
tool_registry = ToolRegistry()
tool_registry.register_tool(CalculatorTool())
tool_registry.register_tool(SearchTool())
tool_registry.register_tool(WeatherTool())

# 创建自定义ReActAgent
agent = MyReActAgent(
    name="我的ReAct助手",
    llm=llm,
    tool_registry=tool_registry,
    max_steps=5,
)

# 测试工具推理问题
question = "请帮我计算 15 * 8 + 32，并说明你使用了哪个工具。"
result = agent.run(question)
print(f"\n最终结果: {result}")

# 查看对话历史
print(f"对话历史: {len(agent.get_history())} 条消息")
