"""MySimpleAgent - 基于 hello-agents SimpleAgent 的第 7.4.1 节实现。"""

import re
from importlib import import_module
from typing import Iterator, Optional

from hello_agents.core.config import Config
from hello_agents.core.llm import HelloAgentsLLM
from hello_agents.core.message import Message
from hello_agents.tools.registry import ToolRegistry

SimpleAgent = import_module("hello_agents.agents.simple_agent").SimpleAgent
HelloAgentsException = import_module("hello_agents.core.exceptions").HelloAgentsException


class MySimpleAgent(SimpleAgent):
    """
    重写的简单对话 Agent。

    对齐教程第 7.4.1 节：继承框架中的 SimpleAgent，保留统一历史记录
    与 LLM 调用接口，并扩展可选工具调用、流式响应和工具管理方法。
    """

    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        tool_registry: Optional[ToolRegistry] = None,
        enable_tool_calling: bool = True,
    ):
        super().__init__(name, llm, system_prompt, config)
        self.tool_registry = tool_registry
        self.enable_tool_calling = enable_tool_calling and tool_registry is not None
        print(f"✅ {name} 初始化完成，工具调用: {'启用' if self.enable_tool_calling else '禁用'}")

    def run(self, input_text: str, max_tool_iterations: int = 3, **kwargs) -> str:
        """运行简单对话逻辑，支持可选工具调用。"""
        print(f"🤖 {self.name} 正在处理: {input_text}")

        messages = []
        messages.append({"role": "system", "content": self._get_enhanced_system_prompt()})

        for msg in self._history:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": input_text})

        if not self.enable_tool_calling:
            response = self.llm.invoke(messages, **kwargs) or ""
            self.add_message(Message(input_text, "user"))
            self.add_message(Message(response, "assistant"))
            print(f"✅ {self.name} 响应完成")
            return response

        return self._run_with_tools(messages, input_text, max_tool_iterations, **kwargs)

    def _get_enhanced_system_prompt(self) -> str:
        """构建包含工具信息的增强系统提示词。"""
        base_prompt = self.system_prompt or "你是一个有用的AI助手。"

        if not self.enable_tool_calling or not self.tool_registry:
            return base_prompt

        tools_description = self.tool_registry.get_tools_description()
        if not tools_description or tools_description == "暂无可用工具":
            return base_prompt

        tools_section = "\n\n## 可用工具\n"
        tools_section += "你可以使用以下工具来帮助回答问题:\n"
        tools_section += tools_description + "\n"
        tools_section += "\n## 工具调用格式\n"
        tools_section += "当需要使用工具时，请使用以下格式:\n"
        tools_section += "`[TOOL_CALL:{tool_name}:{parameters}]`\n"
        tools_section += "例如:`[TOOL_CALL:search:Python编程]` 或 `[TOOL_CALL:calculator:2+3*4]`\n\n"
        tools_section += "工具调用结果会自动插入到对话中，然后你可以基于结果继续回答。\n"

        return base_prompt + tools_section

    def _run_with_tools(self, messages: list, input_text: str, max_tool_iterations: int, **kwargs) -> str:
        """支持多轮工具调用的运行逻辑。"""
        current_iteration = 0
        final_response = ""

        while current_iteration < max_tool_iterations:
            response = self.llm.invoke(messages, **kwargs) or ""
            tool_calls = self._parse_tool_calls(response)

            if tool_calls:
                print(f"🔧 检测到 {len(tool_calls)} 个工具调用")
                tool_results = []
                clean_response = response

                for call in tool_calls:
                    result = self._execute_tool_call(call["tool_name"], call["parameters"])
                    tool_results.append(result)
                    clean_response = clean_response.replace(call["original"], "")

                messages.append({"role": "assistant", "content": clean_response})
                tool_results_text = "\n\n".join(tool_results)
                messages.append({
                    "role": "user",
                    "content": f"工具执行结果:\n{tool_results_text}\n\n请基于这些结果给出完整的回答。",
                })

                current_iteration += 1
                continue

            final_response = response
            break

        if current_iteration >= max_tool_iterations and not final_response:
            final_response = self.llm.invoke(messages, **kwargs) or ""

        self.add_message(Message(input_text, "user"))
        self.add_message(Message(final_response, "assistant"))
        print(f"✅ {self.name} 响应完成")

        return final_response

    def _parse_tool_calls(self, text: str) -> list[dict[str, str]]:
        """解析文本中的工具调用。"""
        pattern = r"\[TOOL_CALL:([^:]+):([^\]]+)\]"
        matches = re.findall(pattern, text)

        tool_calls = []
        for tool_name, parameters in matches:
            tool_calls.append({
                "tool_name": tool_name.strip(),
                "parameters": parameters.strip(),
                "original": f"[TOOL_CALL:{tool_name}:{parameters}]",
            })

        return tool_calls

    def _execute_tool_call(self, tool_name: str, parameters: str) -> str:
        """执行工具调用。"""
        if not self.tool_registry:
            return "❌ 错误:未配置工具注册表"

        try:
            tool = self.tool_registry.get_tool(tool_name)
            if tool:
                param_dict = self._parse_tool_parameters(tool_name, parameters)
                result = tool.run(param_dict)
            else:
                result = self.tool_registry.execute_tool(tool_name, parameters)

            return f"🔧 工具 {tool_name} 执行结果:\n{result}"
        except Exception as exc:
            return f"❌ 工具调用失败:{str(exc)}"

    def _parse_tool_parameters(self, tool_name: str, parameters: str) -> dict[str, str]:
        """智能解析工具参数。"""
        if "=" in parameters:
            param_dict = {}
            pairs = parameters.split(",") if "," in parameters else [parameters]
            for pair in pairs:
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    param_dict[key.strip()] = value.strip()
            return param_dict

        if tool_name == "calculator":
            return {"expression": parameters, "input": parameters}
        if tool_name == "search":
            return {"query": parameters, "input": parameters}
        if tool_name == "weather":
            return {"city": parameters, "input": parameters}
        if tool_name == "memory":
            return {"action": "search", "query": parameters, "input": parameters}
        return {"input": parameters}

    def stream_run(self, input_text: str, **kwargs) -> Iterator[str]:
        """自定义流式运行方法。"""
        print(f"🌊 {self.name} 开始流式处理: {input_text}")

        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        for msg in self._history:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": input_text})

        full_response = ""
        print("📝 实时响应: ", end="")
        try:
            for chunk in self.llm.stream_invoke(messages, **kwargs):
                full_response += chunk
                yield chunk
        except HelloAgentsException as exc:
            if not full_response or "list index out of range" not in str(exc):
                raise
            print("\n⚠️ 检测到空流式结束块，已保留已接收内容并正常结束。")

        print()
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(full_response, "assistant"))
        print(f"✅ {self.name} 流式响应完成")

    def add_tool(self, tool) -> None:
        """添加工具到 Agent。"""
        if not self.tool_registry:
            self.tool_registry = ToolRegistry()
            self.enable_tool_calling = True

        self.tool_registry.register_tool(tool)
        print(f"🔧 工具 '{tool.name}' 已添加")

    def has_tools(self) -> bool:
        """检查是否有可用工具。"""
        return self.enable_tool_calling and self.tool_registry is not None

    def remove_tool(self, tool_name: str) -> bool:
        """移除工具。"""
        if self.tool_registry:
            self.tool_registry.unregister(tool_name)
            return True
        return False

    def list_tools(self) -> list[str]:
        """列出所有可用工具。"""
        if self.tool_registry:
            return self.tool_registry.list_tools()
        return []


# Backward-compatible alias for earlier local demos.
SimpleAgentExt = MySimpleAgent
