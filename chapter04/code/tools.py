"""
第四章工具模块：工具定义与执行器
包含搜索工具和通用工具执行器
"""

import os
from typing import Dict, Any


def search(query: str) -> str:
    """
    使用Tavily Search API进行智能网页搜索。
    功能对标SerpApi：优先返回直接答案，其次返回结构化搜索结果。
    需要在.env中配置TAVILY_API_KEY。
    """
    try:
        from tavily import TavilyClient
        
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "错误：TAVILY_API_KEY 未在 .env 文件中配置。"
        
        # 自动去掉查询中的年份限制，确保获取最新信息
        import re
        query = re.sub(r'\b(20\d{2}|19\d{2})\b', '', query).strip()
        query = re.sub(r'\s+', ' ', query).strip()
        if not query:
            query = "最新信息"
        
        print(f"🔍 正在执行 [Tavily] 网页搜索: {query}")
        
        tavily = TavilyClient(api_key=api_key)
        
        # 使用advanced搜索深度获取更全面的结果
        response = tavily.search(
            query=query,
            search_depth="advanced",
            include_answer=True,
            include_images=False,
            max_results=5
        )
        
        # 1. 优先返回AI综合答案（对标SerpApi的answer_box）
        if response.get("answer"):
            answer = response["answer"]
            print(f"✅ 找到直接答案")
            return f"【直接答案】\n{answer}"
        
        # 2. 其次返回结构化搜索结果（对标SerpApi的organic_results）
        results = response.get("results", [])
        if not results:
            return f"对不起，没有找到关于 '{query}' 的信息。"
        
        # 3. 智能解析：返回前3个最相关结果的摘要
        snippets = []
        for i, result in enumerate(results[:3]):
            title = result.get('title', '无标题')
            content = result.get('content', '')
            url = result.get('url', '')
            
            snippets.append(
                f"[{i+1}] {title}\n"
                f"    摘要: {content[:200]}...\n"
                f"    来源: {url}"
            )
        
        return "【搜索结果】\n" + "\n\n".join(snippets)
        
    except ImportError:
        return "错误：未安装tavily库，请运行 'pip install tavily'"
    except Exception as e:
        return f"搜索时发生错误: {e}"


class ToolExecutor:
    """
    一个工具执行器，负责管理和执行工具。
    """
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}

    def registerTool(self, name: str, description: str, func: callable):
        """
        向工具箱中注册一个新工具。
        """
        if name in self.tools:
            print(f"警告：工具 '{name}' 已存在，将被覆盖。")
        
        self.tools[name] = {"description": description, "func": func}
        print(f"工具 '{name}' 已注册。")

    def getTool(self, name: str) -> callable:
        """
        根据名称获取一个工具的执行函数。
        """
        return self.tools.get(name, {}).get("func")

    def getAvailableTools(self) -> str:
        """
        获取所有可用工具的格式化描述字符串。
        """
        return "\n".join([
            f"- {name}: {info['description']}" 
            for name, info in self.tools.items()
        ])

    def execute(self, name: str, input_str: str) -> str:
        """
        执行指定工具。
        """
        if name not in self.tools:
            return f"错误：未找到名为 '{name}' 的工具。"
        try:
            return self.tools[name]["func"](input_str)
        except Exception as e:
            return f"工具执行错误: {str(e)}"


# --- 工具初始化与使用示例 ---
if __name__ == '__main__':
    # 1. 初始化工具执行器
    toolExecutor = ToolExecutor()

    # 2. 注册搜索工具
    search_description = "一个网页搜索引擎。当你需要回答关于时事、事实以及在你的知识库中找不到的信息时，应使用此工具。"
    toolExecutor.registerTool("Search", search_description, search)
    
    # 3. 打印可用的工具
    print("\n--- 可用的工具 ---")
    print(toolExecutor.getAvailableTools())

    # 4. 智能体的Action调用
    print("\n--- 执行 Action: Search['英伟达最新的GPU型号是什么'] ---")
    tool_name = "Search"
    tool_input = "英伟达最新的GPU型号是什么"

    tool_function = toolExecutor.getTool(tool_name)
    if tool_function:
        observation = tool_function(tool_input)
        print("--- 观察 (Observation) ---")
        print(observation)
    else:
        print(f"错误：未找到名为 '{tool_name}' 的工具。")
