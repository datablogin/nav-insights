"""Core error taxonomy for nav_insights engine.

This module provides a unified error handling system for all parsers and analyzers,
ensuring consistent error types, messages, and severity mappings across the codebase.
Includes both DSL error handling (from main branch) and parser error taxonomy.
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, Optional, Type

from .ir_base import Severity
from . import dsl_exceptions as dslx


class ErrorCode(str, Enum):
    """Standard error codes for consistent error categorization."""

    # Data validation errors
    INVALID_INPUT_DATA = "INVALID_INPUT_DATA"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FIELD_VALUE = "INVALID_FIELD_VALUE"
    NEGATIVE_METRIC_VALUE = "NEGATIVE_METRIC_VALUE"

    # Processing errors
    PARSER_ERROR = "PARSER_ERROR"
    TRANSFORMATION_ERROR = "TRANSFORMATION_ERROR"
    MAPPING_ERROR = "MAPPING_ERROR"

    # Configuration errors
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    MISSING_CONFIGURATION = "MISSING_CONFIGURATION"

    # External service errors
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"
    DATA_SOURCE_ERROR = "DATA_SOURCE_ERROR"

    # System errors
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class CoreError(Exception):
    """Base exception class for all nav_insights errors.

    Provides structured error handling with dual interfaces:
    
    Parser interface (original):
    - error_code: Standardized error categorization 
    - message: Human-readable error description
    - severity: Error severity level (Severity enum)
    - context: Additional context for debugging
    - original_error: Original exception if this wraps another error
    
    DSL interface (compatibility):
    - code: Stable machine-readable code string
    - category: High-level subsystem string
    - severity: String severity level
    """

    def __init__(
        self,
        message: str = None,
        error_code: ErrorCode = None,
        severity: Severity = None,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
        # DSL compatibility interface
        code: str = None,
        category: str = None,
        cause: Optional[Exception] = None,
    ):
        # Handle DSL interface (code, category, message)
        if code is not None and category is not None:
            # DSL interface usage
            self.code = code
            self.category = category
            self.message = message or ""
            self.severity = severity or "error" if isinstance(severity, str) else Severity.medium
            self.context = context or {}
            self.cause = cause
            # Map to parser interface
            self.error_code = ErrorCode.PARSER_ERROR if category == "dsl" else ErrorCode.UNKNOWN_ERROR
            self.original_error = cause
        else:
            # Parser interface usage
            self.message = message or ""
            self.error_code = error_code or ErrorCode.UNKNOWN_ERROR  
            self.severity = severity or Severity.medium
            self.context = context or {}
            self.original_error = original_error
            # Map to DSL interface for compatibility
            self.code = self.error_code.value.lower()
            self.category = "parser"
            self.cause = original_error

        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize error to dictionary (DSL interface compatibility)."""
        data = {
            "code": self.code,
            "category": self.category,
            "severity": self.severity if isinstance(self.severity, str) else self.severity.value,
            "message": self.message,
            "context": self.context,
        }
        if self.cause is not None:
            data["cause"] = type(self.cause).__name__
        return data

    def __str__(self) -> str:
        # Support both DSL and parser interface string representations
        if hasattr(self, 'category') and hasattr(self, 'code'):
            return f"[{self.category}:{self.code}] {self.message}"
        else:
            parts = [f"[{self.error_code.value}] {self.message}"]
            if self.context:
                parts.append(f"Context: {self.context}")
            if self.original_error:
                parts.append(f"Original: {self.original_error}")
            return " | ".join(parts)

    def __repr__(self) -> str:
        return (
            f"CoreError(message={self.message!r}, error_code={self.error_code.value!r}, "
            f"severity={self.severity.value if hasattr(self.severity, 'value') else self.severity!r}, context={self.context!r})"
        )


class ValidationError(CoreError):
    """Error for data validation failures."""

    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
        severity: Severity = Severity.high,
        error_code: ErrorCode = ErrorCode.INVALID_FIELD_VALUE,
        **kwargs,
    ):
        context = kwargs.pop("context", {})
        if field_name:
            context["field_name"] = field_name
        if field_value is not None:
            context["field_value"] = field_value

        super().__init__(
            message=message, error_code=error_code, severity=severity, context=context, **kwargs
        )


class ParserError(CoreError):
    """Error for parser-specific failures."""

    def __init__(
        self,
        message: str,
        parser_name: Optional[str] = None,
        severity: Severity = Severity.high,
        **kwargs,
    ):
        context = kwargs.pop("context", {})
        if parser_name:
            context["parser_name"] = parser_name

        super().__init__(
            message=message,
            error_code=ErrorCode.PARSER_ERROR,
            severity=severity,
            context=context,
            **kwargs,
        )


class NegativeMetricError(ValidationError):
    """Error for negative metric values that should be non-negative."""

    def __init__(self, field_name: str, field_value: Any, message: Optional[str] = None, **kwargs):
        if message is None:
            message = f"Metric '{field_name}' cannot be negative, got: {field_value}"

        super().__init__(
            message=message,
            field_name=field_name,
            field_value=field_value,
            severity=Severity.high,
            error_code=ErrorCode.NEGATIVE_METRIC_VALUE,
            **kwargs,
        )


def wrap_exception(
    exception: Exception,
    message: str,
    error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
    severity: Severity = Severity.medium,
    context: Optional[Dict[str, Any]] = None,
) -> CoreError:
    """Wrap an external exception in a CoreError with additional context."""
    return CoreError(
        message=message,
        error_code=error_code,
        severity=severity,
        context=context,
        original_error=exception,
    )


# DSL-compatible CoreError interface (from main branch)
# This provides compatibility with DSL tests while maintaining parser functionality

# Mapping of known exceptions to CoreError codes/categories
_DSL_EXCEPTION_MAP: Dict[Type[BaseException], Dict[str, str]] = {
    dslx.ParseError: {"code": "parse_error", "category": "dsl"},
    dslx.UnsupportedNodeError: {"code": "unsupported_node", "category": "dsl"},
    dslx.HelperNotFoundError: {"code": "helper_not_found", "category": "dsl"},
    dslx.ResourceLimitError: {"code": "resource_limit", "category": "dsl"},
    dslx.ExpressionError: {"code": "expression_error", "category": "dsl"},
}


def to_core_error(exc: BaseException, *, default_category: str = "unknown") -> CoreError:
    """Convert an arbitrary exception to a CoreError with best-effort mapping.

    Known DSL exceptions are mapped to stable codes; otherwise falls back to
    a generic 'unhandled_exception' code with provided default_category.
    
    This function provides compatibility with the main branch DSL error handling.
    """
    for etype, meta in _DSL_EXCEPTION_MAP.items():
        if isinstance(exc, etype):
            # Use DSL interface for better compatibility
            return CoreError(
                code=meta["code"],
                category=meta["category"],
                message=str(exc),
                severity="error",
                context={},
                cause=exc,
            )
    
    return CoreError(
        code="unhandled_exception",
        category=default_category,
        message=str(exc),
        severity="error",
        context={},
        cause=exc,
    )