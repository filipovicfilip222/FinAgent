"""Sandboxed arithmetic calculator.

Security requirement (non-negotiable in the spec): **no bare ``eval``**. We parse the
expression into an AST and walk it ourselves, allowing only numeric literals and a
small whitelist of arithmetic operators. Anything else — names, attribute access,
function calls, comprehensions, etc. — raises ``CalculatorError``. This means a
malicious or malformed expression like ``__import__('os').system('rm -rf /')`` can
never execute; it is rejected at the parse-walk stage.
"""

from __future__ import annotations

import ast
import operator

from . import register

Number = int | float


class CalculatorError(ValueError):
    """Raised for anything the sandbox refuses to evaluate."""


# Whitelisted binary / unary operators only.
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

# Guard rails so a hostile expression can't burn CPU/memory.
_MAX_POW_EXPONENT = 100
_MAX_ABS_RESULT = 1e300


def _eval_node(node: ast.AST) -> Number:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    # Python 3.8+: literals are ast.Constant
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalculatorError(f"Only numeric literals are allowed, got {node.value!r}.")
        return node.value

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise CalculatorError(f"Operator {op_type.__name__} is not allowed.")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if op_type is ast.Pow and abs(right) > _MAX_POW_EXPONENT:
            raise CalculatorError("Exponent too large.")
        if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
            raise CalculatorError("Division by zero.")
        result = _BIN_OPS[op_type](left, right)
        if isinstance(result, complex):
            raise CalculatorError("Complex results are not supported.")
        if abs(result) > _MAX_ABS_RESULT:
            raise CalculatorError("Result out of range.")
        return result

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise CalculatorError(f"Unary operator {op_type.__name__} is not allowed.")
        return _UNARY_OPS[op_type](_eval_node(node.operand))

    raise CalculatorError(f"Disallowed expression element: {type(node).__name__}.")


def evaluate(expression: str) -> Number:
    """Evaluate a pure-arithmetic expression string safely."""
    if not isinstance(expression, str) or not expression.strip():
        raise CalculatorError("Empty expression.")
    if len(expression) > 500:
        raise CalculatorError("Expression too long.")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError(f"Could not parse expression: {exc.msg}") from exc
    return _eval_node(tree)


def calculate(tool_input: dict) -> str:
    """Tool entry point. Input: {"expression": "<str>"}. Output echoes expr + result."""
    expression = str(tool_input.get("expression", "")).strip()
    value = evaluate(expression)
    # Keep integers clean, round floats for readability while staying precise enough.
    if isinstance(value, float):
        shown = round(value, 6)
        if shown == int(shown):
            shown = int(shown) if abs(value - int(value)) < 1e-9 else shown
    else:
        shown = value
    return f"{expression} = {shown}"


# Registered under the name the planner uses.
register("calculator")(calculate)
