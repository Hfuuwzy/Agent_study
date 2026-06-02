"""
第六章示例代码4: LangGraph 框架 - 三步智能搜索问答助手

实现依据：Hello-Agents 第六章 6.5.2「三步问答助手」中的代码片段。
本文件只做必要组合：定义状态、三个节点、构建图、循环运行。
"""

import os
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from tavily import TavilyClient

from simple_chat_openai import SimpleChatOpenAI


class SearchState(TypedDict):
    messages: Annotated[list, add_messages]
    user_query: str      # 经过LLM理解后的用户需求总结
    search_query: str    # 优化后用于Tavily API的搜索查询
    search_results: str  # Tavily搜索返回的结果
    final_answer: str    # 最终生成的答案
    step: str            # 标记当前步骤


load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

if OPENAI_MODEL is None or OPENAI_API_KEY is None or OPENAI_BASE_URL is None:
    raise RuntimeError("请在 .env 中设置 OPENAI_MODEL、OPENAI_API_KEY、OPENAI_BASE_URL")

llm = SimpleChatOpenAI(
    model=OPENAI_MODEL,
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
)

tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def understand_query_node(state: SearchState) -> dict:
    """步骤1：理解用户查询并生成搜索关键词"""
    user_message = state["messages"][-1].content

    understand_prompt = f"""分析用户的查询："{user_message}"
请完成两个任务：
1. 简洁总结用户想要了解什么
2. 生成最适合搜索引擎的关键词（中英文均可，要精准）

格式：
理解：[用户需求总结]
搜索词：[最佳搜索关键词]"""

    response = llm.invoke([HumanMessage(content=understand_prompt)])
    response_text = response.content

    # 解析LLM的输出，提取搜索关键词
    search_query = user_message  # 默认使用原始查询
    if "搜索词：" in response_text:
        search_query = response_text.split("搜索词：", 1)[1].strip()

    return {
        "user_query": response_text,
        "search_query": search_query,
        "step": "understood",
        "messages": [AIMessage(content=f"我将为您搜索：{search_query}")],
    }


def tavily_search_node(state: SearchState) -> dict:
    """步骤2：使用Tavily API进行真实搜索"""
    search_query = state["search_query"]
    try:
        print(f"🔍 正在搜索: {search_query}")
        response = tavily_client.search(
            query=search_query,
            search_depth="basic",
            max_results=5,
            include_answer=True,
        )

        answer = response.get("answer") or ""
        results = response.get("results") or []
        formatted_results = []
        if answer:
            formatted_results.append(f"Tavily摘要：{answer}")

        for index, item in enumerate(results, start=1):
            title = item.get("title", "无标题")
            url = item.get("url", "")
            content = item.get("content", "")
            formatted_results.append(
                f"[{index}] {title}\n链接：{url}\n内容：{content}"
            )

        search_results = "\n\n".join(formatted_results) or "未搜索到有效结果。"

        return {
            "search_results": search_results,
            "step": "searched",
            "messages": [AIMessage(content="✅ 搜索完成！正在整理答案...")],
        }
    except Exception as e:
        return {
            "search_results": f"搜索失败：{e}",
            "step": "search_failed",
            "messages": [AIMessage(content="❌ 搜索遇到问题...")],
        }


def generate_answer_node(state: SearchState) -> dict:
    """步骤3：基于搜索结果生成最终答案"""
    if state["step"] == "search_failed":
        # 如果搜索失败，执行回退策略，基于LLM自身知识回答
        fallback_prompt = (
            "搜索API暂时不可用，请基于您的知识回答用户的问题：\n"
            f"用户问题：{state['user_query']}"
        )
        response = llm.invoke([HumanMessage(content=fallback_prompt)])
    else:
        # 搜索成功，基于搜索结果生成答案
        answer_prompt = f"""基于以下搜索结果为用户提供完整、准确的答案：
用户问题：{state['user_query']}
搜索结果：
{state['search_results']}
请综合搜索结果，提供准确、有用的回答..."""
        response = llm.invoke([HumanMessage(content=answer_prompt)])

    return {
        "final_answer": response.content,
        "step": "completed",
        "messages": [AIMessage(content=response.content)],
    }


def create_search_assistant():
    workflow = StateGraph(SearchState)

    # 添加节点
    workflow.add_node("understand", understand_query_node)
    workflow.add_node("search", tavily_search_node)
    workflow.add_node("answer", generate_answer_node)

    # 设置线性流程
    workflow.add_edge(START, "understand")
    workflow.add_edge("understand", "search")
    workflow.add_edge("search", "answer")
    workflow.add_edge("answer", END)

    # 编译图
    memory = InMemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app


def main():
    app = create_search_assistant()

    print("🔍 智能搜索助手启动！")
    print("我会使用Tavily API为您搜索最新、最准确的信息")
    print("支持各种问题：新闻、技术、知识问答等")
    print("(输入 'quit' 退出)")

    while True:
        user_query = input("\n🤔 您想了解什么: ").strip()
        if user_query.lower() in {"quit", "exit", "q"}:
            break
        if not user_query:
            continue

        initial_state = {
            "messages": [HumanMessage(content=user_query)],
            "user_query": "",
            "search_query": "",
            "search_results": "",
            "final_answer": "",
            "step": "start",
        }
        config = {"configurable": {"thread_id": "search-assistant"}}

        print("\n" + "=" * 60)
        for event in app.stream(initial_state, config=config):
            if "understand" in event:
                state = event["understand"]
                print(f"🧠 理解阶段: {state['user_query']}")
            elif "search" in event:
                state = event["search"]
                print(f"🔍 搜索阶段: {state['messages'][-1].content}")
            elif "answer" in event:
                state = event["answer"]
                print(f"\n💡 最终回答:\n{state['final_answer']}")
        print("=" * 60)


if __name__ == "__main__":
    main()
