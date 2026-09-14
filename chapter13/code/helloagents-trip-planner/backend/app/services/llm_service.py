"""LLM 构造模块：无进程级单例，只提供按需构造。"""

from .. import config as _config  # noqa: F401  # 保证 load_dotenv() 先于 hello_agents 导入
from hello_agents import HelloAgentsLLM


def create_llm() -> HelloAgentsLLM:
    """构造一个新的 LLM 实例。

    HelloAgentsLLM 会自动从环境变量读取 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL
    等配置；每次调用返回独立实例，便于按 Run 注入或替换为测试桩。
    """
    llm = HelloAgentsLLM()
    print("✅ LLM 服务初始化成功")
    print(f"   提供商: {llm.provider}")
    print(f"   模型: {llm.model}")
    return llm

