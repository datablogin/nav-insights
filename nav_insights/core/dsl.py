from __future__ import annotations
import ast
from typing import Any, Dict


def value(path: str, root: Any, default=None) -> Any:
    """Safely access a dotted path on nested dicts/objects.

    Returns `default` if any segment is missing or None. """
    cur = root
    for part in path.split("."):
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur if cur is not None else default


ALLOWED_FUNCS = {"min": min, "max": max}


class SafeEval(ast.NodeVisitor):
    def __init__(self, ctx: Dict[str, Any]):
        self.ctx = ctx

    def visit(self, node):
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            if node.id in ("True", "False", "None"):
                return {"True": True, "False": False, "None": None}[node.id]
            raise ValueError(f"Name not allowed: {node.id}")
        elif isinstance(node, ast.BinOp):
            left = self.visit(node.left)
            right = self.visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Mod):
                return left % right
            raise ValueError("Operator not allowed")
        elif isinstance(node, ast.BoolOp):
            vals = [self.visit(v) for v in node.values]
            if isinstance(node.op, ast.And):
                out = True
                for v in vals:
                    out = out and v
                return out
            if isinstance(node.op, ast.Or):
                out = False
                for v in vals:
                    out = out or v
                return out
            raise ValueError("Bool op not allowed")
        elif isinstance(node, ast.UnaryOp):
            v = self.visit(node.operand)
            if isinstance(node.op, ast.Not):
                return not v
            if isinstance(node.op, ast.USub):
                return -v
            raise ValueError("Unary op not allowed")
        elif isinstance(node, ast.Compare):
            left = self.visit(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = self.visit(comparator)
                ok = (
                    isinstance(op, ast.Eq)
                    and (left == right)
                    or isinstance(op, ast.NotEq)
                    and (left != right)
                    or isinstance(op, ast.Lt)
                    and (left < right)
                    or isinstance(op, ast.LtE)
                    and (left <= right)
                    or isinstance(op, ast.Gt)
                    and (left > right)
                    or isinstance(op, ast.GtE)
                    and (left >= right)
                )
                if not ok:
                    return False
                left = right
            return True
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "value":
                args = [self.visit(a) for a in node.args]
                if len(args) == 1 and isinstance(args[0], str):
                    return self.ctx["value"](args[0])
                if len(args) == 2 and isinstance(args[0], str):
                    return self.ctx["value"](args[0], args[1])
                raise ValueError("value() requires 'path' or ('path', default)")
            elif isinstance(node.func, ast.Name) and node.func.id in ALLOWED_FUNCS:
                f = ALLOWED_FUNCS[node.func.id]
                args = [self.visit(a) for a in node.args]
                return f(*args)
            else:
                raise ValueError("Function not allowed")
        else:
            raise ValueError(f"Node not allowed: {type(node).__name__}")


def eval_expr(expr: str, root: Any) -> Any:
    tree = ast.parse(expr, mode="eval")
    return SafeEval({"value": lambda p, d=None: value(p, root, d)}).visit(tree)
