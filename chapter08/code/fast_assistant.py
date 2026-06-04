"""
第八章示例：智能文档问答助手
结合 MemoryTool(记忆系统) + RAGTool(检索增强) 实现PDF知识问答

功能：
1. 加载PDF文档到RAG知识库
2. 支持基于文档内容的问答
3. 记忆系统记录学习历程
4. 终端交互式问答
"""
from dotenv import load_dotenv
import os
import time
import json
from typing import Dict, Any, Optional
from datetime import datetime

# 加载环境变量
load_dotenv()

# 导入hello_agents组件
try:
    from hello_agents.tools import MemoryTool, RAGTool
    from hello_agents import HelloAgentsLLM
    HAS_HELLO_AGENTS = True
except ImportError as e:
    print(f"警告: 无法导入hello_agents: {e}")
    print("请确保已安装: pip install hello-agents")
    HAS_HELLO_AGENTS = False
    
    # 定义占位类以避免语法错误
    class MemoryTool:
        def __init__(self, **kwargs):
            raise RuntimeError("MemoryTool需要hello_agents包。请运行: pip install hello-agents")
    
    class RAGTool:
        def __init__(self, **kwargs):
            raise RuntimeError("RAGTool需要hello_agents包。请运行: pip install hello-agents")


class PDFLearningAssistant:
    """智能文档问答助手 - 结合记忆系统和RAG检索"""

    def __init__(self, user_id: str = "default_user"):
        """初始化学习助手
        
        Args:
            user_id: 用户ID，用于隔离不同用户的数据
        """
        self.user_id = user_id
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if not HAS_HELLO_AGENTS:
            raise RuntimeError("请先安装hello_agents包: pip install hello-agents")
        
        # 初始化工具 - 使用外部数据库(Qdrant + Neo4j)
        print("正在初始化记忆系统...")
        self.memory_tool = MemoryTool(
            user_id=user_id,
            memory_types=["working", "episodic", "semantic"]  # 启用多类型记忆
        )
        
        print("正在初始化RAG知识库...")
        self.rag_tool = RAGTool(
            rag_namespace=f"pdf_{user_id}",  # 用户隔离的命名空间
            knowledge_base_path=f"./knowledge_base/{user_id}"
        )
        
        # 学习统计
        self.stats = {
            "session_start": datetime.now(),
            "documents_loaded": 0,
            "questions_asked": 0,
            "concepts_learned": 0
        }
        
        # 当前加载的文档
        self.current_document = None
        
        print("助手初始化完成！")

    def load_document(self, pdf_path: str) -> Dict[str, Any]:
        """加载PDF文档到RAG知识库
        
        使用RAGTool处理PDF:
        1. MarkItDown转换PDF为文本
        2. 智能分块(document chunking)
        3. 向量化存储到Qdrant
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            Dict: 包含success和message的结果
        """
        if not os.path.exists(pdf_path):
            return {"success": False, "message": f"文件不存在: {pdf_path}"}
        
        print(f"\n正在加载PDF: {os.path.basename(pdf_path)}")
        start_time = time.time()
        
        # 【RAGTool】处理PDF: MarkItDown转换 → 智能分块 → 向量化存储到Qdrant
        result = self.rag_tool.execute(
            "add_document",
            file_path=pdf_path,
            chunk_size=1000,      # 每块1000字符
            chunk_overlap=200     # 重叠200字符保证连贯性
        )
        
        process_time = time.time() - start_time
        
        if result.get("success", False):
            self.current_document = os.path.basename(pdf_path)
            self.stats["documents_loaded"] += 1
            
            # 【MemoryTool】记录学习事件到情景记忆
            self.memory_tool.execute(
                "add",
                content=f"加载了文档《{self.current_document}》，包含 {result.get('chunk_count', '?')} 个知识片段",
                memory_type="episodic",
                importance=0.9,
                event_type="document_loaded",
                session_id=self.session_id
            )
            
            return {
                "success": True,
                "message": f"加载成功！提取了 {result.get('chunk_count', '?')} 个知识片段(耗时: {process_time:.1f}秒)",
                "document": self.current_document,
                "chunks": result.get('chunk_count', 0)
            }
        else:
            return {
                "success": False,
                "message": f"加载失败: {result.get('error', '未知错误')}"
            }

    def ask(self, question: str, use_advanced_search: bool = True) -> str:
        """向文档提问 - 结合RAG检索和记忆上下文
        
        Args:
            question: 用户问题
            use_advanced_search: 是否使用高级检索(MQE + HyDE)
            
        Returns:
            str: 基于文档内容的答案
        """
        if not self.current_document:
            return "请先加载文档！使用 load_document(pdf_path)"
        
        print(f"\n正在分析问题: {question}")
        
        # 【MemoryTool】记录问题到工作记忆(短期上下文)
        self.memory_tool.execute(
            "add",
            content=f"用户提问: {question}",
            memory_type="working",
            importance=0.6,
            session_id=self.session_id
        )
        
        # 【RAGTool】使用高级检索从Qdrant获取答案
        # 支持多查询扩展(MQE)和假设性文档嵌入(HyDE)
        print("正在从知识库检索相关信息...")
        answer = self.rag_tool.execute(
            "ask",
            question=question,
            limit=5,                      # 检索Top-5相关片段
            enable_advanced_search=use_advanced_search,
            enable_mqe=use_advanced_search,   # 多查询扩展提高召回
            enable_hyde=use_advanced_search   # HyDE提高精度
        )
        
        # 【MemoryTool】记录问答到情景记忆(长期历史)
        self.memory_tool.execute(
            "add",
            content=f"关于'{question}'的学习: {answer[:200]}...",
            memory_type="episodic",
            importance=0.7,
            event_type="qa_interaction",
            session_id=self.session_id
        )
        
        self.stats["questions_asked"] += 1
        
        return answer

    def add_note(self, content: str, concept: Optional[str] = None):
        """添加学习笔记 - 存储到语义记忆
        
        Args:
            content: 笔记内容
            concept: 相关概念标签
        """
        self.memory_tool.execute(
            "add",
            content=content,
            memory_type="semantic",    # 语义记忆存储知识
            importance=0.8,
            concept=concept or "general",
            session_id=self.session_id
        )
        self.stats["concepts_learned"] += 1
        print(f"笔记已保存: {content[:50]}...")

    def recall(self, query: str, limit: int = 5) -> str:
        """回顾学习历程 - 检索记忆
        
        Args:
            query: 查询关键词
            limit: 返回结果数量
            
        Returns:
            str: 相关记忆内容
        """
        print(f"\n正在检索记忆: {query}")
        result = self.memory_tool.execute(
            "search",
            query=query,
            limit=limit
        )
        return result

    def get_learning_context(self) -> str:
        """获取学习上下文 - 用于增强问答"""
        # 检索相关工作记忆(当前会话上下文)
        working_mem = self.memory_tool.execute(
            "search",
            query="session_id:" + self.session_id,
            memory_type="working",
            limit=3
        )
        
        # 检索相关情景记忆(历史学习记录)
        episodic_mem = self.memory_tool.execute(
            "search",
            query="深度学习 Python 学习",
            memory_type="episodic", 
            limit=2
        )
        
        context = f"""
当前会话: {self.session_id}
工作记忆: {working_mem}
相关历史: {episodic_mem}
"""
        return context

    def get_stats(self) -> Dict[str, Any]:
        """获取学习统计"""
        duration = (datetime.now() - self.stats["session_start"]).total_seconds()
        return {
            "会话时长": f"{duration:.0f}秒",
            "加载文档": self.stats["documents_loaded"],
            "提问次数": self.stats["questions_asked"],
            "学习笔记": self.stats["concepts_learned"],
            "当前文档": self.current_document or "未加载",
            "用户ID": self.user_id
        }

    def generate_report(self, save_to_file: bool = True) -> Dict[str, Any]:
        """生成学习报告"""
        print("\n正在生成学习报告...")
        
        # 获取记忆摘要
        memory_summary = self.memory_tool.execute("summary", limit=10)
        
        # 获取RAG统计
        rag_stats = self.rag_tool.execute("stats")
        
        duration = (datetime.now() - self.stats["session_start"]).total_seconds()
        
        report = {
            "session_info": {
                "session_id": self.session_id,
                "user_id": self.user_id,
                "start_time": self.stats["session_start"].isoformat(),
                "duration_seconds": duration
            },
            "learning_metrics": {
                "documents_loaded": self.stats["documents_loaded"],
                "questions_asked": self.stats["questions_asked"],
                "concepts_learned": self.stats["concepts_learned"]
            },
            "memory_summary": memory_summary,
            "rag_status": rag_stats
        }
        
        if save_to_file:
            report_file = f"learning_report_{self.session_id}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            report["report_file"] = report_file
            print(f"报告已保存: {report_file}")
        
        return report


# ============== 演示代码 ==============
def main():
    """主函数 - 交互式PDF问答"""
    import sys
    import io
    
    # 修复Windows终端编码
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("PDF智能文档问答助手")
    print("=" * 60)
    print("\n功能说明:")
    print("- 加载PDF文档到RAG知识库(Qdrant向量数据库)")
    print("- 使用MemoryTool记录学习历程(Neo4j图数据库)")
    print("- 基于文档内容回答问题\n")
    
    try:
        # 初始化助手
        assistant = PDFLearningAssistant(user_id="test_user")
        
        # 获取PDF路径 - 从项目根目录的notes文件夹
        pdf_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "notes", "Happy-LLM-0727.pdf"
        )
        
        print(f"\n准备加载文档: {pdf_path}")
        
        # 检查PDF文件
        if not os.path.exists(pdf_path):
            print(f"错误: PDF文件不存在: {pdf_path}")
            print("请确保PDF文件放在chapter08/notes/目录下")
            return
        
        # 加载文档
        result = assistant.load_document(pdf_path)
        
        if not result["success"]:
            print(f"加载失败: {result['message']}")
            return
        
        print(result["message"])
        
        # 交互式问答
        print("\n" + "=" * 60)
        print("问答模式 (输入'exit'退出, 'stats'查看统计)")
        print("=" * 60)
        
        while True:
            print()
            question = input("你的问题: ").strip()
            
            if not question:
                continue
            
            if question.lower() in ['exit', 'quit', '退出']:
                break
            
            if question.lower() == 'stats':
                stats = assistant.get_stats()
                for k, v in stats.items():
                    print(f"  {k}: {v}")
                continue
            
            if question.lower() == 'report':
                assistant.generate_report()
                continue
            
            # 回答问题
            answer = assistant.ask(question)
            print(f"\n答案: {answer}")
        
        # 退出时生成报告
        print("\n生成最终报告...")
        report = assistant.generate_report()
        
        print("\n学习统计:")
        stats = assistant.get_stats()
        for k, v in stats.items():
            print(f"  {k}: {v}")
        
        print("\n再见!")
        
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
