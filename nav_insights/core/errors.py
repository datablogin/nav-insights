"""Core error taxonomy for nav_insights engine.

This module provides a unified error handling system for all parsers and analyzers,
ensuring consistent error types, messages, and severity mappings across the codebase.
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, Optional

from .ir_base import Severity


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

    Provides structured error handling with consistent fields:
    - error_code: Standardized error categorization
    - message: Human-readable error description
    - severity: Error severity level
    - context: Additional context for debugging
    - original_error: Original exception if this wraps another error
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        severity: Severity = Severity.medium,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.severity = severity
        self.context = context or {}
        self.original_error = original_error

        super().__init__(self.message)

    def __str__(self) -> str:
        parts = [f"[{self.error_code.value}] {self.message}"]
        if self.context:
            parts.append(f"Context: {self.context}")
        if self.original_error:
            parts.append(f"Original: {self.original_error}")
        return " | ".join(parts)

    def __repr__(self) -> str:
        return (
            f"CoreError(message={self.message!r}, error_code={self.error_code.value!r}, "
            f"severity={self.severity.value!r}, context={self.context!r})"
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
            **kwargs,
        )
        self.error_code = ErrorCode.NEGATIVE_METRIC_VALUE


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
