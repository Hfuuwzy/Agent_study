# test_my_calculator.py
from dotenv import load_dotenv
from my_calculator_tool import create_calculator_registry

# 加载环境变量
load_dotenv()

def test_calculator_tool():
    """测试自定义计算器工具"""

    # 创建包含计算器的注册表
    registry = create_calculator_registry()

    print("🧪 测试自定义计算器工具\n")

    # 简单测试用例
    test_cases = [
        "2 + 3",           # 基本加法
        "10 - 4",          # 基本减法
        "5 * 6",           # 基本乘法
        "15 / 3",          # 基本除法
        "sqrt(16)",        # 平方根
    ]

    for i, expression in enumerate(test_cases, 1):
        print(f"测试 {i}: {expression}")
        result = registry.execute_tool("my_calculator", expression)
        print(f"结果: {result}\n")

def test_with_simple_agent():
    """测试与SimpleAgent的集成"""
    from hello_agents import HelloAgentsLLM
    from hello_agents.core.exceptions import HelloAgentsException

    # 创建LLM客户端
    llm = HelloAgentsLLM()

    # 创建包含计算器的注册表
    registry = create_calculator_registry()

    print("🤖 与SimpleAgent集成测试:")

    # 模拟SimpleAgent使用工具的场景
    user_question = "请帮我计算 sqrt(16) + 2 * 3"

    print(f"用户问题: {user_question}")

    # 使用工具计算
    calc_result = registry.execute_tool("my_calculator", "sqrt(16) + 2 * 3")
    print(f"计算结果: {calc_result}")

    # 构建最终回答
    final_messages = [
        {"role": "user", "content": f"计算结果是 {calc_result}，请用自然语言回答用户的问题:{user_question}"}
    ]

    print("\n🎯 SimpleAgent的回答:")
    response = llm.think(final_messages)
    content_received = False
    full_response = ""
    try:
        for chunk in response:
            content_received = True
            full_response += chunk
            print(chunk, end="", flush=True)
    except HelloAgentsException as exc:
        if not content_received or "list index out of range" not in str(exc):
            raise
        print("\n⚠️ 检测到空流式结束块，已保留已接收内容并正常结束。")
    print("\n")
    
    # 清理并显示最终响应
    import re
    cleaned = re.sub(r'([\u4e00-\u9fa5])\1+', r'\1', full_response)
    cleaned = re.sub(r'(\w)\1{2,}', r'\1\1', cleaned)
    cleaned = re.sub(r'\n+', '\n', cleaned)
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    if cleaned != full_response and cleaned.strip():
        print("📋 清理后的回答:")
        print(cleaned)

if __name__ == "__main__":
    test_calculator_tool()
    test_with_simple_agent()