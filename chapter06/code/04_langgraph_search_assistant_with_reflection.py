"""
第六章示例代码4（扩展版）: LangGraph 框架 - 带反思的智能搜索问答助手

在基础三步流程（理解→搜索→回答）的基础上，添加 Reflection（反思）节点，
实现自我评估和质量改进的循环机制。

流程：
START → understand → search → answer → reflect → (条件分支)
                                          ↓
                                    ┌─────┴─────┐
                                    ↓           ↓
                                  END      (回到 search 改进)
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
    user_query: str
    search_query: str
    search_results: str
    final_answer: str
    reflection_result: str
    needs_improvement: bool
    iteration_count: int
    step: str


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

MAX_ITERATIONS = 2


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

    search_query = user_message
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
    iteration_info = f"（第 {state.get('iteration_count', 1)} 轮生成）" if state.get('iteration_count', 1) > 1 else ""

    if state["step"] == "search_failed":
        fallback_prompt = (
            "搜索API暂时不可用，请基于您的知识回答用户的问题：\n"
            f"用户问题：{state['user_query']}"
        )
        response = llm.invoke([HumanMessage(content=fallback_prompt)])
    else:
        reflection_feedback = ""
        if state.get("reflection_result") and state.get("needs_improvement"):
            reflection_feedback = f"""
上一轮反思反馈：
{state['reflection_result']}

请根据以上反馈改进答案。"""

        answer_prompt = f"""基于以下搜索结果为用户提供完整、准确的答案{iteration_info}：
用户问题：{state['user_query']}
搜索结果：
{state['search_results']}
{reflection_feedback}

请综合搜索结果，提供准确、有用的回答...
注意：
- 直接回答用户问题，不要提及"根据搜索结果"等用语
- 确保信息准确，如果不确定请说明
- 回答要简洁明了"""
        response = llm.invoke([HumanMessage(content=answer_prompt)])

    return {
        "final_answer": response.content,
        "step": "answered",
        "messages": [AIMessage(content=response.content)],
    }


def reflect_node(state: SearchState) -> dict:
    """步骤4（新增）：反思评估答案质量"""
    reflect_prompt = f"""请客观评估以下答案的质量，判断是否需要改进：

原始问题：{state['user_query']}

生成的答案：
{state['final_answer']}

搜索获得的信息：
{state['search_results'][:500]}...

请从以下维度评估（满分10分）：
1. 准确性：答案是否正确回答了问题？
2. 完整性：是否遗漏了重要信息？
3. 相关性：答案是否与问题相关？
4. 清晰度：表达是否清晰易懂？

输出格式：
总评分：[X]/10
评估：[简要说明优点和不足]
需要改进：[是/否]
改进建议：[具体建议，如果需要]"""

    response = llm.invoke([HumanMessage(content=reflect_prompt)])
    reflection_text = response.content

    needs_improvement = "需要改进：是" in reflection_text or "需要改进：是" in reflection_text.replace(" ", "")

    score = 0
    if "总评分：" in reflection_text:
        try:
            score_part = reflection_text.split("总评分：")[1].split("/")[0].strip()
            score = int(score_part)
        except:
            pass

    if score < 6:
        needs_improvement = True

    current_iteration = state.get("iteration_count", 1)
    if current_iteration >= MAX_ITERATIONS:
        needs_improvement = False

    return {
        "reflection_result": reflection_text,
        "needs_improvement": needs_improvement,
        "iteration_count": current_iteration + 1,
        "step": "reflected",
        "messages": [AIMessage(content=f"🤔 反思评估：{'需要改进，重新搜索优化' if needs_improvement else '答案质量良好'}")],
    }


def should_continue(state: SearchState) -> str:
    """条件函数：根据反思结果决定下一步"""
    if state.get("needs_improvement") and state.get("iteration_count", 1) <= MAX_ITERATIONS:
        return "improve"
    return "end"


def create_search_assistant_with_reflection():
    """创建带反思功能的搜索助手"""
    workflow = StateGraph(SearchState)

    workflow.add_node("understand", understand_query_node)
    workflow.add_node("search", tavily_search_node)
    workflow.add_node("answer", generate_answer_node)
    workflow.add_node("reflect", reflect_node)

    workflow.add_edge(START, "understand")
    workflow.add_edge("understand", "search")
    workflow.add_edge("search", "answer")
    workflow.add_edge("answer", "reflect")

    workflow.add_conditional_edges(
        "reflect",
        should_continue,
        {
            "improve": "search",
            "end": END,
        }
    )

    memory = InMemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app


def main():
    app = create_search_assistant_with_reflection()

    print("🔍 智能搜索助手（带反思版）启动！")
    print("我会使用Tavily API为您搜索最新、最准确的信息")
    print("新增功能：自动评估答案质量，必要时重新搜索优化")
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
            "reflection_result": "",
            "needs_improvement": False,
            "iteration_count": 1,
            "step": "start",
        }
        config = {"configurable": {"thread_id": "search-assistant"}}

        print("\n" + "=" * 60)
        for event in app.stream(initial_state, config=config):
            if "understand" in event:
                state = event["understand"]
                print(f"🧠 理解阶段: {state['user_query'][:100]}...")
            elif "search" in event:
                state = event["search"]
                if state.get("iteration_count", 1) > 1:
                    print(f"🔍 重新搜索（第{state['iteration_count']-1}轮优化）")
                else:
                    print(f"🔍 搜索阶段: {state['messages'][-1].content}")
            elif "answer" in event:
                state = event["answer"]
                iteration = state.get("iteration_count", 1)
                if iteration > 1:
                    print(f"\n💡 优化后的答案（第{iteration}轮）:\n{state['final_answer'][:200]}...")
                else:
                    print(f"\n💡 初步答案:\n{state['final_answer'][:200]}...")
            elif "reflect" in event:
                state = event["reflect"]
                print(f"\n🎯 反思评估:\n{state['reflection_result'][:300]}...")
        print("=" * 60)


if __name__ == "__main__":
    main()
