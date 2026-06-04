"""
第八章示例：记忆与RAG结合使用
展示如何同时使用 MemoryTool 和 RAGTool
"""
from dotenv import load_dotenv
import os

load_dotenv()



from hello_agents import SimpleAgent, HelloAgentsLLM, ToolRegistry
from hello_agents.tools import MemoryTool, RAGTool


def demo_memory_and_rag():
    """演示同时使用记忆和RAG的Agent"""
    print("=" * 60)
    print("🧠 + 🔍 记忆与RAG结合演示")
    print("=" * 60)
    
    # 创建 LLM 实例
    llm = HelloAgentsLLM()
    
    # 创建 Agent
    agent = SimpleAgent(
        name="智能助手",
        llm=llm,
        system_prompt="""你是一个拥有记忆能力和知识检索能力的AI助手。
        
        **你必须遵守以下工作流程**：
        1. **首先**调用 `memory` 工具检索用户背景和历史
        2. **如果**需要回答专业问题，**必须**调用 `rag` 工具从知识库检索
        3. **绝对禁止**直接回答，必须先使用工具获取信息
        
        **工具调用格式**：
        - 检索用户记忆：`[TOOL_CALL:memory:action=search&query=用户背景]`
        - 检索知识库：`[TOOL_CALL:rag:action=search&query=问题]`
        
        **重要**：如果你不调用工具，用户将无法获得准确和个性化的回答！
        """
    )
    
    # 创建工具注册表
    tool_registry = ToolRegistry()
    
    # 添加记忆工具
    memory_tool = MemoryTool(user_id="user123")
    tool_registry.register_tool(memory_tool)
    print("✅ 记忆工具已注册")
    
    # 添加 RAG 工具
    rag_tool = RAGTool(knowledge_base_path="./knowledge_base")
    tool_registry.register_tool(rag_tool)
    print("✅ RAG工具已注册")
    
    # 配置工具
    agent.tool_registry = tool_registry
    
    print("\n" + "=" * 60)
    print("场景1: 用户自我介绍（存入记忆）")
    print("=" * 60)
    
    # 存储用户信息到记忆
    memory_tool.execute(
        "add",
        content="用户叫张三，是一名Python开发者，正在学习机器学习",
        memory_type="semantic",
        importance=0.9
    )
    
    memory_tool.execute(
        "add",
        content="张三已经掌握Python基础语法和面向对象编程",
        memory_type="semantic",
        importance=0.8
    )
    
    print("✅ 用户信息已存入记忆系统")
    
    print("\n" + "=" * 60)
    print("场景2: 用户提问（结合记忆和知识检索）")
    print("=" * 60)
    
    # 模拟对话
    conversations = [
        {
            "user": "你好，还记得我是谁吗？",
            "agent_thought": "Agent应该从记忆中检索用户信息"
        },
        {
            "user": "我想学习深度学习，你能给我介绍一下吗？",
            "agent_thought": "Agent应该结合记忆(已知Python基础) + RAG检索深度学习知识"
        },
        {
            "user": "Python装饰器在深度学习中有什么应用？",
            "agent_thought": "Agent应该结合记忆(Python) + RAG检索装饰器知识"
        }
    ]
    
    for i, conv in enumerate(conversations, 1):
        print(f"\n👤 用户 {i}: {conv['user']}")
        print(f"💭 Agent思考: {conv['agent_thought']}")
        
        try:
            response = agent.run(conv['user'])
            print(f"🤖 Agent: {response}")
        except Exception as e:
            print(f"🤖 Agent: [需要配置LLM API和知识库]")
    
    print("\n" + "=" * 60)
    print("场景3: 记忆检索演示")
    print("=" * 60)
    
    print("\n🔍 从记忆中检索用户背景：")
    result = memory_tool.execute("search", query="用户背景 Python", limit=3)
    print(result)
    
    print("\n📊 获取记忆摘要：")
    result = memory_tool.execute("summary")
    print(result)
    
    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)
    print("\n核心要点：")
    print("1. 记忆系统存储用户偏好和历史")
    print("2. RAG系统提供专业知识支持")
    print("3. 两者结合实现个性化、准确的服务")


def demo_architecture():
    """展示记忆+RAG系统的架构"""
    print("\n" + "=" * 60)
    print("🏗️ 记忆与RAG系统架构")
    print("=" * 60)
    
    architecture = """
    ┌─────────────────────────────────────────────────────────┐
    │                    Agent 层                            │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
    │  │ SimpleAgent │  │  ReActAgent │  │ PlanAndSolve│   │
    │  └─────────────┘  └─────────────┘  └─────────────┘   │
    └─────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────┐
    │                   ToolRegistry                         │
    │  ┌───────────────────┐  ┌───────────────────┐        │
    │  │   MemoryTool      │  │     RAGTool       │        │
    │  │  ┌─────────────┐  │  │  ┌─────────────┐  │        │
    │  │  │ MemoryManager│  │  │  │RAG Pipeline│  │        │
    │  │  └─────────────┘  │  │  └─────────────┘  │        │
    │  └───────────────────┘  └───────────────────┘        │
    └─────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │ 记忆类型层   │  │  RAG系统层   │  │  存储层     │
    │             │  │             │  │             │
    │ WorkingMem  │  │ Document    │  │ Qdrant      │
    │ EpisodicMem │  │ Processor   │  │ Neo4j       │
    │ SemanticMem │  │ VectorStore │  │ SQLite      │
    │ PerceptualMem│ │ Retriever   │  │             │
    └─────────────┘  └─────────────┘  └─────────────┘
    
    数据流向：
    1. 用户输入 → Agent 接收
    2. Agent 调用 MemoryTool 检索用户历史
    3. Agent 调用 RAGTool 检索专业知识
    4. 结合记忆+知识 → LLM生成回答
    5. 将对话存入记忆系统
    """
    
    print(architecture)


if __name__ == "__main__":
    print("第八章：记忆与检索 - 综合演示\n")
    
    try:
        # 运行架构展示
        demo_architecture()
        
        # 运行综合演示
        demo_memory_and_rag()
        
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        print("\n提示：请确保已安装 hello-agents 框架并配置好环境变量")
        print("安装命令: pip install 'hello-agents[all]==0.2.0'")
        print("\n需要配置的环境变量：")
        print("- OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL")
        print("- QDRANT_URL / QDRANT_API_KEY")
        print("- NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD")
        print("- EMBED_MODEL_TYPE / EMBED_API_KEY (可选)")
