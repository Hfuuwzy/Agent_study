"""
简易 OpenAI 兼容客户端包装器
绕过 ChatOpenAI 的默认参数注入，直接调用 OpenAI API
"""
from typing import Any, Dict, List, Optional

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)


class SimpleChatOpenAI:
    """
    简易的 OpenAI 兼容聊天模型
    不继承 BaseChatModel，只提供简单的 invoke 接口
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        import openai
        self.model = model
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def invoke(
        self,
        messages: List[BaseMessage],
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AIMessage:
        """
        调用模型，返回 AIMessage

        Args:
            messages: LangChain 消息列表
            config: 配置（暂不使用）

        Returns:
            AIMessage 响应
        """
        openai_messages = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                openai_messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                openai_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                openai_messages.append({"role": "assistant", "content": msg.content})
            else:
                openai_messages.append({"role": "user", "content": str(msg.content)})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
        )

        content = response.choices[0].message.content or ""
        return AIMessage(content=content)

    def __call__(self, *args, **kwargs):
        return self.invoke(*args, **kwargs)
