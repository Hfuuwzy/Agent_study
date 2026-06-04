"""
第八章示例：RAG系统基础演示
展示 RAGTool 的基本用法和检索增强生成
"""
from dotenv import load_dotenv

load_dotenv()

from hello_agents import SimpleAgent, HelloAgentsLLM, ToolRegistry
from hello_agents.tools import RAGTool


def demo_rag_basic():
    """演示 RAG 系统的基础功能"""
    print("=" * 60)
    print("🔍 RAG 系统基础演示")
    print("=" * 60)
    
    # 创建 LLM 实例
    llm = HelloAgentsLLM()
    
    # 创建 Agent
    agent = SimpleAgent(
        name="知识助手",
        llm=llm,
        system_prompt="你是一个基于知识库回答问题的AI助手"
    )
    
    # 创建 RAG 工具
    rag_tool = RAGTool(knowledge_base_path="./knowledge_base")
    tool_registry = ToolRegistry()
    tool_registry.register_tool(rag_tool)
    agent.tool_registry = tool_registry
    
    print("\n" + "=" * 60)
    print("步骤1: 添加文档到知识库")
    print("=" * 60)
    
    # 模拟添加一些知识（实际使用时会从文件加载）
    knowledge_docs = [
        """
        Python装饰器是一种设计模式，用于在不修改原函数代码的情况下，
        为函数添加额外功能。装饰器本质上是一个接收函数作为参数并返回
        新函数的高阶函数。
        
        基本语法：
        @decorator
        def function():
            pass
        """,
        """
        机器学习是人工智能的一个分支，它使计算机系统能够从数据中
        学习并改进性能，而无需进行明确的编程。主要类型包括：
        - 监督学习
        - 无监督学习
        - 强化学习
        """,
        """
        深度学习是机器学习的一个子集，使用多层神经网络来模拟
        人脑的工作方式。它在图像识别、自然语言处理等领域表现出色。
        """
    ]
    
    for i, doc in enumerate(knowledge_docs, 1):
        print(f"\n📄 添加文档 {i}:")
        result = rag_tool.execute("add_text", text=doc, document_id=f"doc_{i}")
        print(f"添加结果: {result}")
    
    print("\n" + "=" * 60)
    print("步骤2: 基础检索演示")
    print("=" * 60)
    
    # 基础检索
    queries = [
        "什么是Python装饰器",
        "机器学习有哪些类型",
        "深度学习和机器学习的关系"
    ]
    
    for query in queries:
        print(f"\n🔍 查询: {query}")
        try:
            result = rag_tool.execute("search", query=query, top_k=2)
            print(f"结果: {result}")
        except Exception as e:
            print(f"检索结果: [需要配置知识库才能检索]")
    
    print("\n" + "=" * 60)
    print("步骤3: 使用 MQE (多查询扩展)")
    print("=" * 60)
    
    query = "Python高级特性"
    print(f"\n🔍 查询: {query}")
    print("使用 MQE 扩展查询，提高召回率...")
    try:
        result = rag_tool.execute(
            "search",
            query=query,
            top_k=3,
            use_mqe=True
        )
        print(f"结果: {result}")
    except Exception as e:
        print(f"检索结果: [需要配置知识库才能检索]")
    
    print("\n" + "=" * 60)
    print("步骤4: 使用 HyDE (假设性文档嵌入)")
    print("=" * 60)
    
    query = "神经网络工作原理"
    print(f"\n🔍 查询: {query}")
    print("使用 HyDE 生成假设答案，提高准确性...")
    try:
        result = rag_tool.execute(
            "search",
            query=query,
            top_k=3,
            use_hyde=True
        )
        print(f"结果: {result}")
    except Exception as e:
        print(f"检索结果: [需要配置知识库才能检索]")
    
    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)


def demo_rag_with_agent():
    """演示 Agent 使用 RAG 功能回答问题"""
    print("\n" + "=" * 60)
    print("🤖 Agent + RAG 对话演示")
    print("=" * 60)
    
    # 创建 LLM 实例
    llm = HelloAgentsLLM()
    
    # 创建 Agent（带 RAG 能力）
    agent = SimpleAgent(
        name="知识助手",
        llm=llm,
        system_prompt="""你是一个知识丰富的AI助手。
        当回答问题时，请优先从知识库中检索相关信息，
        然后基于检索结果给出准确、有依据的回答。
        """
    )
    
    # 创建 RAG 工具
    rag_tool = RAGTool(knowledge_base_path="./knowledge_base")
    tool_registry = ToolRegistry()
    tool_registry.register_tool(rag_tool)
    agent.tool_registry = tool_registry
    
    # 模拟用户提问
    questions = [
        "请解释什么是Python装饰器",
        "机器学习的主要类型有哪些？",
        "深度学习和传统机器学习的区别是什么？"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\n👤 用户 {i}: {question}")
        print("🤖 Agent 正在检索知识库...")
        try:
            response = agent.run(question)
            print(f"🤖 Agent: {response}")
        except Exception as e:
            print(f"🤖 Agent: [需要配置知识库和 LLM API]")
    
    print("\n" + "=" * 60)


def demo_comparison():
    """对比不使用 RAG 和使用 RAG 的效果"""
    print("\n" + "=" * 60)
    print("📊 RAG 效果对比演示")
    print("=" * 60)
    
    llm = HelloAgentsLLM()
    
    # 不使用 RAG 的 Agent
    agent_no_rag = SimpleAgent(
        name="普通助手",
        llm=llm,
        system_prompt="你是一个AI助手"
    )
    
    # 使用 RAG 的 Agent
    agent_with_rag = SimpleAgent(
        name="知识助手",
        llm=llm,
        system_prompt="你是一个基于知识库回答问题的AI助手"
    )
    
    # 添加 RAG 工具
    rag_tool = RAGTool(knowledge_base_path="./knowledge_base")
    tool_registry = ToolRegistry()
    tool_registry.register_tool(rag_tool)
    agent_with_rag.tool_registry = tool_registry
    
    question = "什么是Python装饰器？"
    
    print(f"\n❓ 问题: {question}")
    
    print("\n--- 不使用 RAG 的回答 ---")
    try:
        response_no_rag = agent_no_rag.run(question)
        print(response_no_rag)
    except Exception as e:
        print("[需要配置 LLM API]")
    
    print("\n--- 使用 RAG 的回答 ---")
    try:
        response_with_rag = agent_with_rag.run(question)
        print(response_with_rag)
    except Exception as e:
        print("[需要配置知识库和 LLM API]")
    
    print("\n" + "=" * 60)
    print("对比说明：")
    print("- 不使用 RAG：依赖模型内部知识，可能不够准确或详细")
    print("- 使用 RAG：从知识库检索相关信息，回答更准确、有依据")
    print("=" * 60)


if __name__ == "__main__":
    print("第八章：记忆与检索 - RAG演示\n")
    
    try:
        # 运行 RAG 基础演示
        demo_rag_basic()
        
        # 运行 Agent + RAG 演示
        demo_rag_with_agent()
        
        # 运行效果对比
        demo_comparison()
        
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        print("\n提示：请确保已安装 hello-agents 框架并配置好环境变量")
        print("安装命令: pip install 'hello-agents[all]==0.2.0'")
        print("\n需要配置的环境变量：")
        print("- OPENAI_API_KEY / OPENAI_BASE_URL")
        print("- QDRANT_URL / QDRANT_API_KEY")
        print("- NEO4J_URI / NEO4J_PASSWORD")
