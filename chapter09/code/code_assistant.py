"""
长时程代码助手示例
演示上下文工程在实际项目中的应用
"""
import os
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import json


# ==================== 数据结构 ====================

@dataclass
class ContextPacket:
    """候选信息包"""
    content: str
    timestamp: datetime
    token_count: int
    relevance_score: float = 0.5
    metadata: Optional[Dict] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ContextConfig:
    """上下文构建配置"""
    max_tokens: int = 3000
    reserve_ratio: float = 0.2
    min_relevance: float = 0.1
    recency_weight: float = 0.3
    relevance_weight: float = 0.7


# ==================== 简化版工具 ====================

class SimpleNoteTool:
    """简化版笔记工具"""
    
    def __init__(self, workspace_path: str = "."):
        self.workspace_path = Path(workspace_path)
        self.notes_dir = self.workspace_path / "notes"
        self.notes_dir.mkdir(exist_ok=True)
        self.notes_file = self.notes_dir / "notes.json"
        self.notes = self._load_notes()
    
    def _load_notes(self):
        if self.notes_file.exists():
            with open(self.notes_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_notes(self):
        with open(self.notes_file, 'w', encoding='utf-8') as f:
            json.dump(self.notes, f, ensure_ascii=False, indent=2)
    
    def execute(self, action: str, **kwargs) -> str:
        if action == "create":
            note_id = f"note_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.notes[note_id] = {
                "id": note_id,
                "title": kwargs.get("title", ""),
                "content": kwargs.get("content", ""),
                "created": datetime.now().isoformat(),
                "tags": kwargs.get("tags", []),
                "importance": kwargs.get("importance", 0.5)
            }
            self._save_notes()
            return f"笔记已创建: {note_id}"
        elif action == "search":
            query = kwargs.get("query", "").lower()
            results = []
            for note_id, note in self.notes.items():
                if query in note["title"].lower() or query in note["content"].lower():
                    results.append(note)
            return f"找到 {len(results)} 条相关笔记"
        return "未知操作"


class SimpleTerminalTool:
    """简化版终端工具"""
    
    def __init__(self, workspace_path: str = "."):
        self.workspace_path = Path(workspace_path)
    
    def execute(self, action: str, **kwargs) -> str:
        if action == "search":
            pattern = kwargs.get("pattern", "*.py")
            results = []
            for item in self.workspace_path.rglob(pattern):
                if item.is_file():
                    results.append(str(item.relative_to(self.workspace_path)))
            return f"找到 {len(results)} 个文件"
        elif action == "read":
            path = kwargs.get("path", "")
            target = self.workspace_path / path
            if target.exists():
                try:
                    with open(target, 'r', encoding='utf-8') as f:
                        content = f.read()
                    return f"文件内容 ({len(content)} 字符):\n{content[:500]}..."
                except:
                    return "读取失败"
            return "文件不存在"
        return "未知操作"


class SimpleMemoryTool:
    """简化版记忆工具"""
    
    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.memories = []
    
    def execute(self, action: str, **kwargs) -> str:
        if action == "add":
            content = kwargs.get("content", "")
            self.memories.append({
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "importance": kwargs.get("importance", 0.5)
            })
            return f"记忆已添加 (共 {len(self.memories)} 条)"
        elif action == "search":
            query = kwargs.get("query", "").lower()
            results = [m for m in self.memories if query in m["content"].lower()]
            return f"找到 {len(results)} 条相关记忆"
        return "未知操作"


# ==================== 上下文构建器 ====================

class ContextBuilder:
    """上下文构建器，实现 GSSC 流水线"""
    
    def __init__(self, memory_tool=None, config: ContextConfig = None):
        self.memory_tool = memory_tool
        self.config = config or ContextConfig()
    
    def _count_tokens(self, text: str) -> int:
        """估算token数量"""
        chinese_chars = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
        english_words = len([w for w in text.split() if w])
        return int(chinese_chars + english_words * 1.3)
    
    def _calculate_relevance(self, content: str, query: str) -> float:
        """计算相关性"""
        content_words = set(content.lower().split())
        query_words = set(query.lower().split())
        if not query_words:
            return 0.0
        intersection = content_words & query_words
        union = content_words | query_words
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_recency(self, timestamp: datetime) -> float:
        """计算新近性"""
        import math
        age_hours = (datetime.now() - timestamp).total_seconds() / 3600
        decay_factor = 0.1
        recency_score = math.exp(-decay_factor * age_hours / 24)
        return max(0.1, min(1.0, recency_score))
    
    def build(self, user_query: str, conversation_history: List[str] = None, 
              system_instructions: str = "") -> str:
        """构建上下文（GSSC流水线）"""
        packets = []
        
        # 1. Gather: 收集信息
        if system_instructions:
            packets.append(ContextPacket(
                content=system_instructions,
                timestamp=datetime.now(),
                token_count=self._count_tokens(system_instructions),
                relevance_score=1.0,
                metadata={"type": "system_instruction"}
            ))
        
        if conversation_history:
            for msg in conversation_history[-5:]:
                packets.append(ContextPacket(
                    content=msg,
                    timestamp=datetime.now(),
                    token_count=self._count_tokens(msg),
                    relevance_score=0.6,
                    metadata={"type": "conversation"}
                ))
        
        # 2. Select: 选择信息
        available_tokens = int(self.config.max_tokens * (1 - self.config.reserve_ratio))
        selected = []
        current_tokens = 0
        
        for packet in packets:
            if packet.relevance_score == 0.5:
                packet.relevance_score = self._calculate_relevance(packet.content, user_query)
            
            if packet.relevance_score >= self.config.min_relevance:
                if current_tokens + packet.token_count <= available_tokens:
                    selected.append(packet)
                    current_tokens += packet.token_count
        
        # 3. Structure: 结构化输出
        sections = []
        
        if system_instructions:
            sections.append(f"[Role & Policies]\n{system_instructions}")
        
        sections.append(f"[Task]\n{user_query}")
        
        if conversation_history:
            context = "\n".join(conversation_history[-3:])
            sections.append(f"[Context]\n{context}")
        
        sections.append("[Output]\n请基于以上信息，提供准确、有据的回答。")
        
        return "\n\n".join(sections)


# ==================== 代码助手Agent ====================

class CodeAssistantAgent:
    """具有上下文感知能力的代码助手"""
    
    def __init__(self, workspace_path: str = "."):
        self.workspace_path = workspace_path
        
        # 初始化工具
        self.note_tool = SimpleNoteTool(workspace_path)
        self.terminal = SimpleTerminalTool(workspace_path)
        self.memory_tool = SimpleMemoryTool(user_id="code_assistant")
        
        # 初始化上下文构建器
        self.context_builder = ContextBuilder(
            memory_tool=self.memory_tool,
            config=ContextConfig(max_tokens=2000)
        )
        
        self.conversation_history = []
    
    def run(self, user_input: str) -> str:
        """运行Agent"""
        print(f"\n{'='*60}")
        print(f"用户输入: {user_input}")
        print(f"{'='*60}")
        
        # 1. 探索代码库
        print("\n[1. 探索代码库]")
        code_context = self._explore_codebase(user_input)
        print(code_context)
        
        # 2. 获取相关笔记
        print("\n[2. 获取相关笔记]")
        notes_context = self._get_relevant_notes(user_input)
        print(notes_context)
        
        # 3. 构建上下文
        print("\n[3. 构建上下文]")
        optimized_context = self.context_builder.build(
            user_query=user_input,
            conversation_history=self.conversation_history,
            system_instructions="你是代码助手，专注于代码分析和重构建议。请提供具体、可行的建议。"
        )
        print(optimized_context)
        
        # 4. 生成回答（模拟）
        response = self._generate_response(user_input, code_context, notes_context)
        
        # 5. 更新历史和笔记
        self.conversation_history.append(f"用户: {user_input}")
        self.conversation_history.append(f"助手: {response[:200]}...")
        
        self._save_to_notes(user_input, response)
        self.memory_tool.execute("add", content=f"讨论了: {user_input}", importance=0.6)
        
        return response
    
    def _explore_codebase(self, query: str) -> str:
        """探索代码库"""
        # 搜索相关文件
        results = self.terminal.execute("search", pattern="*.py")
        return f"代码库探索结果:\n{results}"
    
    def _get_relevant_notes(self, query: str) -> str:
        """获取相关笔记"""
        results = self.note_tool.execute("search", query=query)
        return f"笔记检索结果:\n{results}"
    
    def _generate_response(self, query: str, code_context: str, notes_context: str) -> str:
        """生成回答（模拟LLM）"""
        # 这里模拟LLM生成回答
        # 实际应用中会调用真正的LLM
        
        if "内存" in query or "memory" in query.lower():
            return """## Pandas内存优化建议

### 1. 数据类型优化
```python
# 使用category类型替代object
df['category'] = df['category'].astype('category')

# 使用更小的数值类型
df['age'] = df['age'].astype('int32')  # 而不是int64
```

### 2. 分块读取大文件
```python
# 使用chunksize参数
chunks = pd.read_csv('large.csv', chunksize=10000)
for chunk in chunks:
    process(chunk)
```

### 3. 使用nullable类型
```python
# 使用nullable整数类型
df['count'] = df['count'].astype('Int64')
```

### 4. 删除不需要的列
```python
df = df.drop(columns=['unnecessary_column'])
```

### 5. 使用适当的数据类型
```python
# 对于字符串列，考虑使用category
df['status'] = df['status'].astype('category')
```

这些方法可以显著减少内存占用，特别是在处理大型数据集时。"""
        
        elif "路由" in query or "route" in query.lower():
            return """## Flask路由最佳实践

### 1. RESTful风格
```python
@app.route('/api/v1/users', methods=['GET'])
def get_users():
    return jsonify(users)

@app.route('/api/v1/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    return jsonify(get_user_by_id(user_id))
```

### 2. 版本控制
```python
@app.route('/api/v1/resource')
@app.route('/api/v2/resource')
def resource():
    pass
```

### 3. 错误处理
```python
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500
```

### 4. 使用蓝图
```python
from flask import Blueprint

api = Blueprint('api', __name__)

@api.route('/users')
def get_users():
    pass
```

### 5. 认证和授权
```python
from functools import wraps

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated
```"""
        
        else:
            return f"""## 关于您的问题

基于对代码库的分析，我提供以下建议：

### 分析结果
1. 代码库中找到了相关文件
2. 笔记中有相关的最佳实践

### 建议
1. 首先检查现有代码结构
2. 参考已有的最佳实践笔记
3. 逐步重构，避免一次性大改

### 下一步
- 具体查看相关文件
- 制定详细的重构计划
- 编写测试用例

如果您需要更具体的建议，请提供更多的上下文信息。"""
    
    def _save_to_notes(self, question: str, answer: str):
        """保存到笔记"""
        self.note_tool.execute("create",
            title=f"Q&A: {question[:30]}...",
            content=f"**问题**: {question}\n\n**回答**: {answer[:200]}...",
            tags=["qa", "code"],
            importance=0.6
        )


def main():
    """演示长时程代码助手"""
    print("=" * 80)
    print("长时程代码助手示例")
    print("=" * 80)
    
    # 创建代码助手
    assistant = CodeAssistantAgent(workspace_path=".")
    
    # 模拟多轮对话
    queries = [
        "如何优化Pandas的内存占用？",
        "Flask路由有什么最佳实践？",
        "帮我分析一下这个项目的代码结构"
    ]
    
    for query in queries:
        response = assistant.run(query)
        print(f"\n助手回答:\n{response}")
        print("\n" + "-" * 80)
    
    # 显示会话历史
    print("\n" + "=" * 80)
    print("会话历史:")
    print("=" * 80)
    for msg in assistant.conversation_history:
        print(msg)
    
    # 显示创建的笔记
    print("\n" + "=" * 80)
    print("创建的笔记:")
    print("=" * 80)
    result = assistant.note_tool.execute("list")
    print(result)
    
    print("\n" + "=" * 80)
    print("示例完成")
    print("=" * 80)


if __name__ == "__main__":
    main()