"""
第八章示例：记忆系统基础演示
展示 MemoryTool 的基本用法
"""

from dotenv import load_dotenv

load_dotenv()

from hello_agents import SimpleAgent, HelloAgentsLLM, ToolRegistry
from hello_agents.tools import MemoryTool


def demo_memory_basic():
    """演示记忆系统的基础功能"""
    print("=" * 60)
    print("🧠 记忆系统基础演示")
    print("=" * 60)
    
    # 创建 LLM 实例
    llm = HelloAgentsLLM()
    
    # 创建 Agent
    agent = SimpleAgent(
        name="记忆助手",
        llm=llm,
        system_prompt="你是一个有记忆能力的AI助手"
    )
    
    # 创建记忆工具
    memory_tool = MemoryTool(user_id="user123")
    tool_registry = ToolRegistry()
    tool_registry.register_tool(memory_tool)
    agent.tool_registry = tool_registry
    
    print("\n" + "=" * 60)
    print("步骤1: 添加多个记忆")
    print("=" * 60)
    
    # 添加第一个记忆（语义记忆）
    result1 = memory_tool.execute(
        "add",
        content="用户张三是一名Python开发者，专注于机器学习和数据分析",
        memory_type="semantic",
        importance=0.8
    )
    print(f"✅ {result1}")
    
    # 添加第二个记忆
    result2 = memory_tool.execute(
        "add",
        content="李四是前端工程师，擅长React和Vue.js开发",
        memory_type="semantic",
        importance=0.7
    )
    print(f"✅ {result2}")
    
    # 添加第三个记忆
    result3 = memory_tool.execute(
        "add",
        content="王五是产品经理，负责用户体验设计和需求分析",
        memory_type="semantic",
        importance=0.6
    )
    print(f"✅ {result3}")
    
    print("\n" + "=" * 60)
    print("步骤2: 搜索特定记忆")
    print("=" * 60)
    
    # 搜索前端相关的记忆
    print("\n🔍 搜索 '前端工程师':")
    result = memory_tool.execute("search", query="前端工程师", limit=3)
    print(result)
    
    print("\n" + "=" * 60)
    print("步骤3: 记忆摘要")
    print("=" * 60)
    
    result = memory_tool.execute("summary")
    print(result)
    
    print("\n" + "=" * 60)
    print("步骤4: 不同记忆类型的使用")
    print("=" * 60)
    
    # 1. 工作记忆 - 临时信息
    print("\n💼 添加工作记忆:")
    result = memory_tool.execute(
        "add",
        content="用户刚才问了关于Python函数的问题",
        memory_type="working",
        importance=0.6
    )
    print(result)
    
    # 2. 情景记忆 - 具体事件
    print("\n📅 添加情景记忆:")
    result = memory_tool.execute(
        "add",
        content="2024年3月15日，用户张三完成了第一个Python项目",
        memory_type="episodic",
        importance=0.8,
        event_type="milestone",
        location="在线学习平台"
    )
    print(result)
    
    # 3. 语义记忆 - 抽象知识
    print("\n📚 添加语义记忆:")
    result = memory_tool.execute(
        "add",
        content="Python是一种解释型、面向对象的编程语言",
        memory_type="semantic",
        importance=0.9,
        knowledge_type="factual"
    )
    print(result)
    
    print("\n" + "=" * 60)
    print("步骤5: 遗忘机制演示")
    print("=" * 60)
    
    # 基于重要性的遗忘
    print("\n🧹 执行遗忘（基于重要性）:")
    result = memory_tool.execute(
        "forget",
        strategy="importance_based",
        threshold=0.3
    )
    print(result)
    
    print("\n" + "=" * 60)
    print("步骤6: 记忆整合")
    print("=" * 60)
    
    # 将工作记忆整合为情景记忆
    print("\n🔄 整合记忆（工作记忆 → 情景记忆）:")
    result = memory_tool.execute(
        "consolidate",
        from_type="working",
        to_type="episodic",
        importance_threshold=0.5
    )
    print(result)
    
    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)


def demo_memory_with_agent():
    """演示 Agent 使用记忆功能"""
    print("\n" + "=" * 60)
    print("🤖 Agent 记忆对话演示")
    print("=" * 60)
    
    # 创建 LLM 实例
    llm = HelloAgentsLLM()
    
    # 创建 Agent
    agent = SimpleAgent(
        name="智能助手",
        llm=llm,
        system_prompt="你是一个有记忆能力的AI助手，记住用户的信息"
    )
    
    # 创建记忆工具
    memory_tool = MemoryTool(user_id="demo_user")
    tool_registry = ToolRegistry()
    tool_registry.register_tool(memory_tool)
    agent.tool_registry = tool_registry
    
    # 模拟对话
    conversations = [
        "你好！请记住我叫张三，我是一名Python开发者",
        "我喜欢使用Django框架开发Web应用",
        "请问你能记住我的名字吗？",
        "我擅长什么技术？"
    ]
    
    for i, user_input in enumerate(conversations, 1):
        print(f"\n👤 用户 {i}: {user_input}")
        response = agent.run(user_input)
        print(f"🤖 Agent: {response}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("第八章：记忆与检索 - 基础演示\n")
    
    try:
        # 运行基础演示
        demo_memory_basic()
        
        # 运行 Agent 对话演示
        demo_memory_with_agent()
        
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        print("\n提示：请确保已安装 hello-agents 框架并配置好环境变量")
        print("安装命令: pip install 'hello-agents[all]==0.2.0'")
