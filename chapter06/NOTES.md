# Chapter 06 学习笔记

## 核心收获

本章学习了四大Agent框架：

| 框架 | 核心理念 | 关键组件 |
|------|---------|---------|
| AutoGen | 对话驱动协作 | AssistantAgent, UserProxyAgent, RoundRobinGroupChat |
| AgentScope | 消息驱动架构 | Msg, MsgHub, DialogAgent, fanout_pipeline |
| CAMEL | 角色扮演 | RolePlaying, Inception Prompting |
| LangGraph | 图结构工作流 | StateGraph, Node, Edge, Conditional Edges |

## Bug修复记录

1. **AutoGen配置错误**：统一使用 OPENAI_* 环境变量
2. **AgentScope Pydantic错误**：使用 model_validate_json 替代直接实例化
3. **CAMEL output_language冲突**：移除重复参数传递
4. **LangGraph InvalidParameter**：创建 SimpleChatOpenAI 绕过不支持参数
5. **system-only message被拒绝**：改为使用 HumanMessage

## 关键实现

- SimpleChatOpenAI: Kimi兼容包装器，只传递必要参数
- Reflection扩展: 新增反思节点，条件边实现循环优化

## 文件产出

chapter06/code/:
- 01_autogen_bitcoin.py
- 02_agentscope_werewolf_v2.py
- 03_camel_ebook.py
- 04_langgraph_search_assistant.py
- 04_langgraph_search_assistant_with_reflection.py
- simple_chat_openai.py

学习日期: 2026-06-01
