# 配置好同级文件夹下.env中的大模型API
from dotenv import load_dotenv
import os

# 加载.env文件
load_dotenv()

from hello_agents import SimpleAgent, HelloAgentsLLM, ToolRegistry
from hello_agents.tools import MemoryTool, RAGTool

# 创建LLM实例
llm = HelloAgentsLLM()

# 创建Agent
agent = SimpleAgent(
    name="智能助手",
    llm=llm,
    system_prompt="你是一个有记忆和知识检索能力的AI助手"
)

# 创建工具注册表
tool_registry = ToolRegistry()

# 添加记忆工具
memory_tool = MemoryTool(user_id="user123")
tool_registry.register_tool(memory_tool)

# 添加RAG工具
rag_tool = RAGTool(knowledge_base_path="./knowledge_base")
tool_registry.register_tool(rag_tool)

# 为Agent配置工具
# agent.tool_registry = tool_registry
# 创建Agent（在初始化时传入 tool_registry）
agent = SimpleAgent(
    name="智能助手",
    llm=llm,
    system_prompt="你是一个有记忆和知识检索能力的AI助手",
    tool_registry=tool_registry,  # 在这里传入！
    enable_tool_calling=True
)

# 开始对话
# response = agent.run("你好！请记住我叫张三，我是一名Python开发者")
response = agent.run("张三是谁")
print(response)