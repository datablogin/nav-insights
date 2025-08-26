from __future__ import annotations

class ExpressionError(Exception):
    """Base exception for DSL expression evaluation errors."""
    pass

class ParseError(ExpressionError):
    """Exception raised for syntax errors in expressions."""
    pass

class UnsupportedNodeError(ExpressionError):
    """Exception raised for unsupported AST nodes."""
    pass

class HelperNotFoundError(ExpressionError):
    """Exception raised when a helper function is not found."""
    pass

class ResourceLimitError(ExpressionError):
    """Exception raised when resource limits are exceeded."""
    pass

