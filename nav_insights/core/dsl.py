from __future__ import annotations
import ast
import operator as op
from typing import Any, Dict, Callable, Optional

# Import exceptions from stable module to avoid class identity issues across reloads
from .dsl_exceptions import (
    ExpressionError,
    ParseError,
    UnsupportedNodeError,
    HelperNotFoundError,
    ResourceLimitError,
)


def value(path: str, root: Any, default=None) -> Any:
    """Safely access a dotted path on nested dicts/objects.

    Returns `default` if any segment is missing or None.

    Security: Only supports dict-like access and Pydantic models.
    Does not allow arbitrary attribute access to minimize attack surface.

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
        elif hasattr(cur, "model_dump"):
            # Pydantic model - convert to dict for safe access
            try:
                cur = cur.model_dump().get(part)
            except Exception:
                return default
        elif hasattr(cur, "__getitem__") and hasattr(cur, "get"):
            # Dict-like object with get method
            try:
                cur = cur.get(part)
            except Exception:
                return default
        else:
            # Unsupported object type - reject for security
            return default
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


# Operator mapping for comparisons
COMPARISON_OPS = {
    ast.Eq: op.eq,
    ast.NotEq: op.ne,
    ast.Lt: op.lt,
    ast.LtE: op.le,
    ast.Gt: op.gt,
    ast.GtE: op.ge,
}

# Arithmetic operator mapping
ARITHMETIC_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Mod: op.mod,
}

# Unary operator mapping
UNARY_OPS = {
    ast.Not: op.not_,
    ast.USub: op.neg,
}


class SafeEval(ast.NodeVisitor):
    """Safe AST evaluator with resource limits and graceful None handling."""

    def __init__(
        self, ctx: Dict[str, Any], registry: Optional[DSLRegistry] = None, max_depth: int = 25
    ):
        self.ctx = ctx
        self.registry = registry or _registry
        self.max_depth = max_depth
        self.current_depth = 0

    def visit(self, node):
        # Check depth limit
        self.current_depth += 1
        if self.current_depth > self.max_depth:
            raise ResourceLimitError(f"Expression AST depth exceeds limit of {self.max_depth}")

        try:
            if isinstance(node, ast.Expression):
                return self.visit(node.body)
            elif isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.Name):
                if node.id in ("True", "False", "None"):
                    return {"True": True, "False": False, "None": None}[node.id]
                raise UnsupportedNodeError(f"Name not allowed: {node.id}")
            elif isinstance(node, ast.BinOp):
                return self._handle_binop(node)
            elif isinstance(node, ast.BoolOp):
                return self._handle_boolop(node)
            elif isinstance(node, ast.UnaryOp):
                return self._handle_unaryop(node)
            elif isinstance(node, ast.Compare):
                return self._handle_compare(node)
            elif isinstance(node, ast.Call):
                return self._handle_call(node)
            else:
                raise UnsupportedNodeError(f"Node not allowed: {type(node).__name__}")
        finally:
            self.current_depth -= 1

    def _handle_binop(self, node: ast.BinOp) -> Any:
        """Handle binary operations with graceful None handling."""
        left = self.visit(node.left)
        right = self.visit(node.right)

        # Graceful None handling for arithmetic operations
        if left is None or right is None:
            return None

        op_func = ARITHMETIC_OPS.get(type(node.op))
        if not op_func:
            raise UnsupportedNodeError(f"Binary operator not allowed: {type(node.op).__name__}")

        try:
            return op_func(left, right)
        except (TypeError, ZeroDivisionError, ValueError) as e:
            raise ExpressionError(f"Arithmetic error: {e}")

    def _handle_boolop(self, node: ast.BoolOp) -> Any:
        """Handle boolean operations with proper short-circuiting and None semantics.

        Rules:
        - Treat None as False in boolean contexts
        - Preserve Python-like short-circuiting
        - Preserve operand values: return the first falsy (for AND) or first truthy (for OR) operand value
          with the special-case that None is coerced to False in the return when it would otherwise propagate
        """
        if isinstance(node.op, ast.And):
            last_val = None
            for operand in node.values:
                val = self.visit(operand)
                if val is None:
                    return False
                if not val:
                    return val
                last_val = val
            return last_val
        elif isinstance(node.op, ast.Or):
            last_val = None
            for operand in node.values:
                val = self.visit(operand)
                if val:
                    return val
                last_val = val
            return False if last_val is None else last_val
        else:
            raise UnsupportedNodeError(f"Boolean operator not allowed: {type(node.op).__name__}")

    def _handle_unaryop(self, node: ast.UnaryOp) -> Any:
        """Handle unary operations."""
        operand = self.visit(node.operand)

        op_func = UNARY_OPS.get(type(node.op))
        if not op_func:
            raise UnsupportedNodeError(f"Unary operator not allowed: {type(node.op).__name__}")

        try:
            return op_func(operand)
        except (TypeError, ValueError) as e:
            raise ExpressionError(f"Unary operation error: {e}")

    def _handle_compare(self, node: ast.Compare) -> Any:
        """Handle comparison operations with graceful None handling."""
        left = self.visit(node.left)

        for op_node, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)

            # Special handling for None comparisons
            if left is None and right is None:
                # None == None is True, other comparisons with None are False
                result = isinstance(op_node, ast.Eq)
            elif left is None or right is None:
                # One is None, other is not: only != is True
                result = isinstance(op_node, ast.NotEq)
            else:
                # Normal comparison
                op_func = COMPARISON_OPS.get(type(op_node))
                if not op_func:
                    raise UnsupportedNodeError(
                        f"Comparison operator not allowed: {type(op_node).__name__}"
                    )

                try:
                    result = op_func(left, right)
                except (TypeError, ValueError) as e:
                    raise ExpressionError(f"Comparison error: {e}")

            if not result:
                return False
            left = right  # For chained comparisons
        return True

    def _handle_call(self, node: ast.Call) -> Any:
        """Handle function calls."""
        if not isinstance(node.func, ast.Name):
            raise UnsupportedNodeError("Only simple function calls allowed")

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
                raise ExpressionError("value() requires 'path' or ('path', default)")
            else:
                # For other accessors, pass all args
                accessor_func = accessor_factory(self.ctx.get("root"))
                return accessor_func(*args)

        # Try registered functions
        func = self.registry.get_function(func_name)
        if func:
            args = [self.visit(a) for a in node.args]
            try:
                return func(*args)
            except Exception as e:
                raise ExpressionError(f"Function '{func_name}' error: {e}")

        # Legacy compatibility - check ALLOWED_FUNCS
        if func_name in ALLOWED_FUNCS:
            f = ALLOWED_FUNCS[func_name]
            args = [self.visit(a) for a in node.args]
            try:
                return f(*args)
            except Exception as e:
                raise ExpressionError(f"Built-in function '{func_name}' error: {e}")

        raise HelperNotFoundError(f"Function '{func_name}' not found")


def eval_expr(
    expr: str,
    root: Any,
    registry: Optional[DSLRegistry] = None,
    max_length: int = 1024,
    max_depth: int = 25,
) -> Any:
    """Evaluate a DSL expression safely against a root data structure.

    Args:
        expr: DSL expression string to evaluate
        root: Root data structure to evaluate against
        registry: Optional registry for custom functions/accessors
        max_length: Maximum allowed expression length in characters
        max_depth: Maximum allowed AST depth

    Returns:
        Result of expression evaluation

    Raises:
        ResourceLimitError: If expression exceeds length or depth limits
        ParseError: If expression has invalid syntax
        ExpressionError: If expression evaluation fails
        UnsupportedNodeError: If expression contains disallowed operations
        HelperNotFoundError: If a function is not found
    """
    # Check expression length limit
    if len(expr) > max_length:
        raise ResourceLimitError(f"Expression length {len(expr)} exceeds limit of {max_length}")

    # Parse with proper error handling
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ParseError(f"Expression syntax error: {e}")

    ctx = {"value": lambda p, d=None: value(p, root, d), "root": root}
    return SafeEval(ctx, registry, max_depth).visit(tree)
