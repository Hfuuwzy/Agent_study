"""
第四章基础组件: HelloAgentsLLM
封装基础LLM调用函数，支持流式响应
"""

import os
from typing import List, Dict
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class HelloAgentsLLM:
    """
    为Hello Agents定制的LLM客户端。
    支持任何兼容OpenAI接口的服务，默认使用流式响应。
    """
    
    def __init__(
        self,
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        timeout: int = None
    ):
        """
        初始化客户端。优先使用传入参数，否则从环境变量加载。
        """
        self.model = model or os.getenv("OPENAI_MODEL")
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        base_url = base_url or os.getenv("OPENAI_BASE_URL")
        timeout = timeout or int(os.getenv("LLM_TIMEOUT", "60"))
        
        if not all([self.model, api_key, base_url]):
            raise ValueError(
                "模型ID、API密钥和服务地址必须被提供或在.env文件中定义。"
            )
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout
        )
    
    def think(self, messages: List[Dict[str, str]], temperature: float = 0) -> str:
        """
        调用大语言模型进行思考，并返回其响应。
        
        Args:
            messages: 消息列表，每个消息包含role和content
            temperature: 温度参数，控制输出的随机性
            
        Returns:
            模型的完整响应文本
        """
        print(f"[思考] 正在调用 {self.model} 模型...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                stream=True
            )
            
            print("[成功] 大语言模型响应成功:")
            collected_content = []
            
            for chunk in response:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content or ""
                print(content, end="", flush=True)
                collected_content.append(content)
            
            print()  # 流式输出结束后换行
            return "".join(collected_content)
            
        except Exception as e:
            print(f"[错误] 调用LLM API时发生错误: {e}")
            return None


# 使用示例
if __name__ == '__main__':
    try:
        # 初始化客户端（自动从.env加载配置）
        llm_client = HelloAgentsLLM()
        
        # 示例对话
        example_messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": "你好！请简单介绍一下Transformer架构。"
            }
        ]
        
        print("--- 调用LLM ---")
        response_text = llm_client.think(example_messages, temperature=0.7)
        
        if response_text:
            print("\n\n--- 完整响应 ---")
            print(response_text)
        
    except ValueError as e:
        print(f"初始化错误: {e}")
        print("请确保.env文件中配置了OPENAI_MODEL、OPENAI_API_KEY和OPENAI_BASE_URL")
