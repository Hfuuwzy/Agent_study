"""
终端工具示例
演示 TerminalTool 的基本使用
"""
import os
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class FileInfo:
    """文件信息"""
    path: str
    name: str
    size: int
    is_dir: bool
    modified: str


class SimpleTerminalTool:
    """简化版终端工具，演示文件系统操作和即时上下文检索"""
    
    def __init__(self, workspace_path: str = "."):
        self.workspace_path = Path(workspace_path)
    
    def execute(self, action: str, **kwargs) -> str:
        """执行终端操作"""
        if action == "list":
            return self._list_files(**kwargs)
        elif action == "read":
            return self._read_file(**kwargs)
        elif action == "search":
            return self._search_files(**kwargs)
        elif action == "info":
            return self._get_info(**kwargs)
        elif action == "find":
            return self._find_files(**kwargs)
        else:
            return f"未知操作: {action}"
    
    def _list_files(self, path: str = ".", max_depth: int = 2) -> str:
        """列出文件和目录"""
        target_path = self.workspace_path / path
        
        if not target_path.exists():
            return f"路径不存在: {path}"
        
        output = f"目录内容: {path}\n\n"
        
        def list_dir(dir_path: Path, depth: int = 0):
            if depth > max_depth:
                return
            
            try:
                items = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
                for item in items:
                    prefix = "  " * depth
                    if item.is_dir():
                        output_lines.append(f"{prefix}📁 {item.name}/")
                        list_dir(item, depth + 1)
                    else:
                        size = item.stat().st_size
                        size_str = self._format_size(size)
                        output_lines.append(f"{prefix}📄 {item.name} ({size_str})")
            except PermissionError:
                output_lines.append(f"{prefix}⚠️  权限不足")
        
        output_lines = [output]
        list_dir(target_path)
        
        return "\n".join(output_lines)
    
    def _read_file(self, path: str, max_lines: int = 100) -> str:
        """读取文件内容"""
        target_path = self.workspace_path / path
        
        if not target_path.exists():
            return f"文件不存在: {path}"
        
        if target_path.is_dir():
            return f"这是一个目录，不是文件: {path}"
        
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            display_lines = lines[:max_lines]
            
            output = f"文件: {path}\n"
            output += f"总行数: {total_lines}\n"
            output += f"显示前 {len(display_lines)} 行:\n\n"
            output += "=" * 60 + "\n"
            
            for i, line in enumerate(display_lines, 1):
                output += f"{i:4d} | {line}"
            
            if total_lines > max_lines:
                output += f"\n... 还有 {total_lines - max_lines} 行未显示\n"
            
            output += "=" * 60
            
            return output
        except UnicodeDecodeError:
            return f"文件编码错误，可能是二进制文件: {path}"
        except Exception as e:
            return f"读取文件失败: {e}"
    
    def _search_files(self, pattern: str = "*.py", query: str = None, max_results: int = 20) -> str:
        """搜索文件"""
        results = []
        
        def search_dir(dir_path: Path):
            try:
                for item in dir_path.rglob(pattern):
                    if item.is_file():
                        # 如果有查询，检查文件内容
                        if query:
                            try:
                                with open(item, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                    if query.lower() in content.lower():
                                        results.append(item)
                            except:
                                pass
                        else:
                            results.append(item)
            except PermissionError:
                pass
        
        search_dir(self.workspace_path)
        
        # 限制结果数量
        results = results[:max_results]
        
        if not results:
            return f"未找到匹配的文件 (模式: {pattern}, 查询: {query})"
        
        output = f"找到 {len(results)} 个文件:\n\n"
        for item in results:
            relative_path = item.relative_to(self.workspace_path)
            size = item.stat().st_size
            size_str = self._format_size(size)
            output += f"- {relative_path} ({size_str})\n"
        
        return output
    
    def _get_info(self, path: str) -> str:
        """获取文件/目录信息"""
        target_path = self.workspace_path / path
        
        if not target_path.exists():
            return f"路径不存在: {path}"
        
        stat = target_path.stat()
        
        output = f"路径信息: {path}\n\n"
        output += f"类型: {'目录' if target_path.is_dir() else '文件'}\n"
        output += f"大小: {self._format_size(stat.st_size)}\n"
        output += f"修改时间: {self._format_time(stat.st_mtime)}\n"
        output += f"权限: {oct(stat.st_mode)[-3:]}\n"
        
        if target_path.is_dir():
            try:
                item_count = sum(1 for _ in target_path.iterdir())
                output += f"包含项目数: {item_count}\n"
            except PermissionError:
                output += "包含项目数: 权限不足\n"
        
        return output
    
    def _find_files(self, keyword: str, max_results: int = 20) -> str:
        """根据文件名关键词查找文件"""
        results = []
        
        def search_dir(dir_path: Path):
            try:
                for item in dir_path.rglob("*"):
                    if item.is_file() and keyword.lower() in item.name.lower():
                        results.append(item)
            except PermissionError:
                pass
        
        search_dir(self.workspace_path)
        
        # 限制结果数量
        results = results[:max_results]
        
        if not results:
            return f"未找到包含 '{keyword}' 的文件"
        
        output = f"找到 {len(results)} 个文件:\n\n"
        for item in results:
            relative_path = item.relative_to(self.workspace_path)
            output += f"- {relative_path}\n"
        
        return output
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}TB"
    
    def _format_time(self, timestamp: float) -> str:
        """格式化时间戳"""
        from datetime import datetime
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def main():
    """演示终端工具的使用"""
    print("=" * 80)
    print("终端工具 (TerminalTool) 示例")
    print("=" * 80)
    
    # 1. 创建终端工具
    terminal = SimpleTerminalTool(workspace_path=".")
    
    # 2. 列出当前目录
    print("\n1. 列出当前目录:")
    result = terminal.execute("list", path=".", max_depth=1)
    print(result)
    
    # 3. 查找Python文件
    print("\n2. 查找Python文件:")
    result = terminal.execute("search", pattern="*.py", max_results=10)
    print(result)
    
    # 4. 搜索包含特定内容的文件
    print("\n3. 搜索包含 'ContextBuilder' 的文件:")
    result = terminal.execute("search", pattern="*.py", query="ContextBuilder")
    print(result)
    
    # 5. 读取文件内容
    print("\n4. 读取 context_builder_demo.py:")
    result = terminal.execute("read", path="chapter09/code/context_builder_demo.py", max_lines=30)
    print(result)
    
    # 6. 获取文件信息
    print("\n5. 获取文件信息:")
    result = terminal.execute("info", path="chapter09/code/context_builder_demo.py")
    print(result)
    
    # 7. 根据关键词查找文件
    print("\n6. 根据关键词 'demo' 查找文件:")
    result = terminal.execute("find", keyword="demo")
    print(result)
    
    print("\n" + "=" * 80)
    print("终端工具示例完成")
    print("=" * 80)


if __name__ == "__main__":
    main()