"""
结构化笔记示例
演示 NoteTool 的基本使用
"""
import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Note:
    """笔记数据结构"""
    id: str
    title: str
    content: str
    created: str
    updated: str
    tags: List[str]
    importance: float = 0.5


class SimpleNoteTool:
    """简化版笔记工具，演示结构化笔记的核心功能"""
    
    def __init__(self, workspace_path: str = "."):
        self.workspace_path = Path(workspace_path)
        self.notes_dir = self.workspace_path / "notes"
        self.notes_dir.mkdir(exist_ok=True)
        self.notes_file = self.notes_dir / "notes.json"
        self.notes = self._load_notes()
    
    def _load_notes(self) -> Dict[str, Note]:
        """加载笔记"""
        if self.notes_file.exists():
            with open(self.notes_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {k: Note(**v) for k, v in data.items()}
        return {}
    
    def _save_notes(self):
        """保存笔记"""
        data = {k: asdict(v) for k, v in self.notes.items()}
        with open(self.notes_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _generate_id(self) -> str:
        """生成笔记ID"""
        return f"note_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def execute(self, action: str, **kwargs) -> str:
        """执行笔记操作"""
        if action == "create":
            return self._create_note(**kwargs)
        elif action == "search":
            return self._search_notes(**kwargs)
        elif action == "update":
            return self._update_note(**kwargs)
        elif action == "delete":
            return self._delete_note(**kwargs)
        elif action == "list":
            return self._list_notes()
        else:
            return f"未知操作: {action}"
    
    def _create_note(self, title: str, content: str, tags: List[str] = None, importance: float = 0.5) -> str:
        """创建笔记"""
        note_id = self._generate_id()
        now = datetime.now().isoformat()
        
        note = Note(
            id=note_id,
            title=title,
            content=content,
            created=now,
            updated=now,
            tags=tags or [],
            importance=importance
        )
        
        self.notes[note_id] = note
        self._save_notes()
        
        return f"笔记已创建: {note_id} - {title}"
    
    def _search_notes(self, query: str, limit: int = 5) -> str:
        """搜索笔记"""
        results = []
        query_lower = query.lower()
        
        for note in self.notes.values():
            # 简单的关键词匹配
            score = 0
            if query_lower in note.title.lower():
                score += 2
            if query_lower in note.content.lower():
                score += 1
            for tag in note.tags:
                if query_lower in tag.lower():
                    score += 1
            
            if score > 0:
                results.append((score, note))
        
        # 按分数排序
        results.sort(key=lambda x: x[0], reverse=True)
        results = results[:limit]
        
        if not results:
            return f"未找到与 '{query}' 相关的笔记"
        
        output = f"找到 {len(results)} 条相关笔记:\n\n"
        for score, note in results:
            output += f"- [{note.id}] {note.title} (重要性: {note.importance})\n"
            output += f"  标签: {', '.join(note.tags)}\n"
            output += f"  内容预览: {note.content[:100]}...\n\n"
        
        return output
    
    def _update_note(self, note_id: str, content: str = None, title: str = None) -> str:
        """更新笔记"""
        if note_id not in self.notes:
            return f"笔记 {note_id} 不存在"
        
        note = self.notes[note_id]
        if title:
            note.title = title
        if content:
            note.content = content
        note.updated = datetime.now().isoformat()
        
        self._save_notes()
        return f"笔记已更新: {note_id}"
    
    def _delete_note(self, note_id: str) -> str:
        """删除笔记"""
        if note_id not in self.notes:
            return f"笔记 {note_id} 不存在"
        
        del self.notes[note_id]
        self._save_notes()
        return f"笔记已删除: {note_id}"
    
    def _list_notes(self) -> str:
        """列出所有笔记"""
        if not self.notes:
            return "暂无笔记"
        
        output = f"共 {len(self.notes)} 条笔记:\n\n"
        for note in self.notes.values():
            output += f"- [{note.id}] {note.title}\n"
            output += f"  创建时间: {note.created}\n"
            output += f"  标签: {', '.join(note.tags)}\n\n"
        
        return output


def main():
    """演示笔记工具的使用"""
    print("=" * 80)
    print("结构化笔记 (NoteTool) 示例")
    print("=" * 80)
    
    # 1. 创建笔记工具
    note_tool = SimpleNoteTool(workspace_path=".")
    
    # 2. 创建笔记
    print("\n1. 创建笔记:")
    result = note_tool.execute("create",
        title="Pandas内存优化",
        content="""## 优化策略

1. 使用category类型替代object
2. 分块读取大文件
3. 使用nullable类型减少内存

## 示例代码

```python
import pandas as pd

# 读取时指定数据类型
df = pd.read_csv('data.csv', dtype={'category': 'category'})

# 分块读取
chunks = pd.read_csv('large.csv', chunksize=10000)
```
""",
        tags=["python", "pandas", "memory"],
        importance=0.8
    )
    print(result)
    
    result = note_tool.execute("create",
        title="Flask路由最佳实践",
        content="""## 路由设计原则

1. RESTful 风格
2. 版本控制
3. 错误处理

## 示例

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/v1/users/<int:user_id>')
def get_user(user_id):
    return jsonify({'user_id': user_id})
```
""",
        tags=["python", "flask", "web"],
        importance=0.7
    )
    print(result)
    
    result = note_tool.execute("create",
        title="项目TODO列表",
        content="""## 待办事项

- [ ] 完成用户认证模块
- [ ] 添加单元测试
- [x] 设计数据库Schema
- [x] 搭建开发环境

## 进行中

- 优化API响应时间
- 重构错误处理逻辑
""",
        tags=["todo", "project"],
        importance=0.9
    )
    print(result)
    
    # 3. 搜索笔记
    print("\n2. 搜索笔记:")
    result = note_tool.execute("search", query="pandas")
    print(result)
    
    result = note_tool.execute("search", query="flask")
    print(result)
    
    result = note_tool.execute("search", query="todo")
    print(result)
    
    # 4. 列出所有笔记
    print("\n3. 所有笔记:")
    result = note_tool.execute("list")
    print(result)
    
    # 5. 更新笔记
    print("\n4. 更新笔记:")
    # 先获取笔记ID
    notes = note_tool.notes
    if notes:
        note_id = list(notes.keys())[0]
        result = note_tool.execute("update",
            note_id=note_id,
            content="## 更新后的优化策略\n\n1. 使用category类型\n2. 分块读取\n3. 使用nullable类型\n4. **新增**: 使用Arrow替代Pandas"
        )
        print(result)
        
        # 查看更新后的笔记
        updated_note = notes[note_id]
        print(f"\n更新后的笔记内容:\n{updated_note.content}")
    
    print("\n" + "=" * 80)
    print("笔记工具示例完成")
    print("=" * 80)


if __name__ == "__main__":
    main()