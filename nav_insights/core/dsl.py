from __future__ import annotations
import ast
from typing import Any, Dict, Callable, Optional


def value(path: str, root: Any, default=None) -> Any:
    """Safely access a dotted path on nested dicts/objects.

    Returns `default` if any segment is missing or None.

    Graceful None behavior:
    - If any segment in the path is None, returns `default`
    - If the final value is None, returns `default`
    - This prevents AttributeError/KeyError exceptions during path traversal
    """
    cur = root
    for part in path.split("."):
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur if cur is not None else default


class DSLRegistry:
    """Registry for DSL functions and accessors that can be extended by domain packs.

    This allows domain-specific functionality to be registered without modifying core DSL code.
    All registered functions must be safe and cannot access arbitrary system resources.
    """

    def __init__(self):
        self._functions: Dict[str, Callable] = {
            "min": min,
            "max": max,
        }
        self._accessors: Dict[str, Callable] = {
            "value": self._make_value_accessor,
        }

    def register_function(self, name: str, func: Callable) -> None:
        """Register a safe function for use in DSL expressions.

        Args:
            name: Function name as it appears in expressions
            func: Callable that implements the function

        Raises:
            ValueError: If name is already registered
        """
        if name in self._functions:
            raise ValueError(f"Function '{name}' is already registered")
        if not callable(func):
            raise ValueError(f"Function '{name}' must be callable")
        self._functions[name] = func

    def register_accessor(self, name: str, func: Callable) -> None:
        """Register a safe accessor function for use in DSL expressions.

        Args:
            name: Accessor name as it appears in expressions
            func: Callable that creates the accessor given a root context

        Raises:
            ValueError: If name is already registered
        """
        if name in self._accessors:
            raise ValueError(f"Accessor '{name}' is already registered")
        if not callable(func):
            raise ValueError(f"Accessor '{name}' must be callable")
        self._accessors[name] = func

    def get_function(self, name: str) -> Optional[Callable]:
        """Get a registered function by name."""
        return self._functions.get(name)

    def get_accessor(self, name: str) -> Optional[Callable]:
        """Get a registered accessor by name."""
        return self._accessors.get(name)

    def list_functions(self) -> Dict[str, Callable]:
        """Return a copy of all registered functions."""
        return self._functions.copy()

    def list_accessors(self) -> Dict[str, Callable]:
        """Return a copy of all registered accessors."""
        return self._accessors.copy()

    def clear(self) -> None:
        """Clear all registered functions and accessors (except built-ins)."""
        self._functions = {"min": min, "max": max}
        self._accessors = {"value": self._make_value_accessor}

    def _make_value_accessor(self, root: Any) -> Callable:
        """Create a value accessor function bound to a root context."""

        def value_fn(path: str, default=None):
            return value(path, root, default)

        return value_fn


# Global registry instance
_registry = DSLRegistry()


def get_registry() -> DSLRegistry:
    """Get the global DSL registry instance."""
    return _registry


def register_dsl_function(name: str, func: Callable) -> None:
    """Convenience function to register a DSL function globally."""
    _registry.register_function(name, func)


def register_dsl_accessor(name: str, func: Callable) -> None:
    """Convenience function to register a DSL accessor globally."""
    _registry.register_accessor(name, func)


# Legacy compatibility - maintaining the old ALLOWED_FUNCS for backward compatibility
ALLOWED_FUNCS = {"min": min, "max": max}


class SafeEval(ast.NodeVisitor):
    def __init__(self, ctx: Dict[str, Any], registry: Optional[DSLRegistry] = None):
        self.ctx = ctx
        self.registry = registry or _registry

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
            if isinstance(node.func, ast.Name):
                func_name = node.func.id

                # Try registered accessors first
                accessor_factory = self.registry.get_accessor(func_name)
                if accessor_factory:
                    args = [self.visit(a) for a in node.args]
                    # Special handling for value accessor
                    if func_name == "value":
                        if len(args) == 1 and isinstance(args[0], str):
                            return self.ctx["value"](args[0])
                        if len(args) == 2 and isinstance(args[0], str):
                            return self.ctx["value"](args[0], args[1])
                        raise ValueError("value() requires 'path' or ('path', default)")
                    else:
                        # For other accessors, pass all args
                        accessor_func = accessor_factory(self.ctx.get("root"))
                        return accessor_func(*args)

                # Try registered functions
                func = self.registry.get_function(func_name)
                if func:
                    args = [self.visit(a) for a in node.args]
                    return func(*args)

                # Legacy compatibility - check ALLOWED_FUNCS
                if func_name in ALLOWED_FUNCS:
                    f = ALLOWED_FUNCS[func_name]
                    args = [self.visit(a) for a in node.args]
                    return f(*args)

                raise ValueError(f"Function '{func_name}' not allowed")
            else:
                raise ValueError("Function not allowed")
        else:
            raise ValueError(f"Node not allowed: {type(node).__name__}")


def eval_expr(expr: str, root: Any, registry: Optional[DSLRegistry] = None) -> Any:
    """Evaluate a DSL expression safely against a root data structure.

    Args:
        expr: DSL expression string to evaluate
        root: Root data structure to evaluate against
        registry: Optional registry for custom functions/accessors

    Returns:
        Result of expression evaluation

    Raises:
        ValueError: If expression contains disallowed operations
        SyntaxError: If expression has invalid syntax
    """
    tree = ast.parse(expr, mode="eval")
    ctx = {"value": lambda p, d=None: value(p, root, d), "root": root}
    return SafeEval(ctx, registry).visit(tree)
