"""计算器工具 - 对齐当前安装版 hello-agents Tool API。"""

import ast
import operator
from importlib import import_module
from typing import Any

_tool_base = import_module("hello_agents.tools.base")
Tool = _tool_base.Tool
ToolParameter = _tool_base.ToolParameter


class CalculatorTool(Tool):
    """执行基础数学表达式计算。"""

    _OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def __init__(self):
        super().__init__(
            name="calculator",
            description="执行数学计算，支持加减乘除、括号和幂运算",
        )

    def run(self, parameters: dict[str, Any]) -> str:
        """执行计算并返回字符串结果。"""
        expression = str(parameters.get("expression") or parameters.get("input") or "").strip()
        if not expression:
            return "错误：参数 'expression' 不能为空。"

        try:
            result = self._evaluate(expression)
            return f"{expression} = {result}"
        except ZeroDivisionError:
            return "错误：除数不能为零。"
        except Exception as exc:
            return f"错误：计算失败: {str(exc)}"

    def get_parameters(self) -> list[ToolParameter]:
        """定义工具参数。"""
        return [
            ToolParameter(
                name="expression",
                type="string",
                description="数学表达式，如 '2 + 3 * 4'",
                required=True,
            )
        ]

    def _evaluate(self, expression: str) -> int | float:
        tree = ast.parse(expression, mode="eval")
        return self._eval_node(tree.body)

    def _eval_node(self, node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in self._OPERATORS:
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return self._OPERATORS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._OPERATORS:
            operand = self._eval_node(node.operand)
            return self._OPERATORS[type(node.op)](operand)
        raise ValueError("表达式包含不支持的语法。")
