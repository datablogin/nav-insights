from __future__ import annotations
from typing import Any, Dict, Optional, Type
from enum import Enum

from .ir_base import Severity
from . import dsl_exceptions as dslx


class CoreError(Exception):
    """Structured error used across core and integrations.

    Attributes:
        message: Human-readable message
        error_code: ErrorCode enum value
        severity: Severity enum value or string (legacy)
        context: Optional structured context payload safe to log/serialize
        original_error: Optional wrapped exception
        code: Optional legacy string code
        category: Optional legacy string category
    """

    def __init__(
        self,
        message: str = None,
        error_code: "ErrorCode" = None,
        severity: Severity | str = Severity.medium,
        *,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[BaseException] = None,
        # Legacy kwargs
        code: Optional[str] = None,
        category: Optional[str] = None,
        **legacy_kwargs: Any,
    ) -> None:
        # Support legacy signature: CoreError(code=..., category=..., message=..., severity="error", context={})
        if message is None and "message" in legacy_kwargs:
            message = legacy_kwargs["message"]
        super().__init__(message or "")
        self.message = message or ""
        self.error_code = error_code if error_code is not None else ErrorCode.UNKNOWN_ERROR
        self.severity = severity
        self.context = context or {}
        self.original_error = original_error
        # Legacy fields
        self.code = code
        self.category = category

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "error_code": self.error_code.name,
            "severity": self.severity.value
            if hasattr(self.severity, "value")
            else str(self.severity),
            "message": self.message,
            "context": self.context,
        }
        if self.original_error is not None:
            data["original_error"] = type(self.original_error).__name__
        # Include legacy keys if present
        if getattr(self, "code", None) is not None:
            data["code"] = self.code
        if getattr(self, "category", None) is not None:
            data["category"] = self.category
        return data

    def __str__(self) -> str:  # pragma: no cover - convenience
        base = f"[{self.error_code.name}] {self.message}"
        if self.original_error is not None:
            return f"{base} (Original: {self.original_error})"
        return base


# Mapping of known exceptions to CoreError codes/categories
_DSL_EXCEPTION_MAP: Dict[Type[BaseException], Dict[str, str]] = {
    dslx.ParseError: {"code": "parse_error", "category": "dsl"},
    dslx.UnsupportedNodeError: {"code": "unsupported_node", "category": "dsl"},
    dslx.HelperNotFoundError: {"code": "helper_not_found", "category": "dsl"},
    dslx.ResourceLimitError: {"code": "resource_limit", "category": "dsl"},
    dslx.ExpressionError: {"code": "expression_error", "category": "dsl"},
}


class ErrorCode(str, Enum):
    INVALID_INPUT_DATA = "invalid_input_data"
    INVALID_FIELD_VALUE = "invalid_field_value"
    PARSER_ERROR = "parser_error"
    NEGATIVE_METRIC_VALUE = "negative_metric_value"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    UNKNOWN_ERROR = "unknown_error"


class ValidationError(CoreError):
    def __init__(
        self,
        message: str,
        *,
        field_name: Optional[str] = None,
        field_value: Any = None,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[BaseException] = None,
        error_code: Optional[ErrorCode] = None,
    ) -> None:
        ctx = context.copy() if context else {}
        if field_name is not None:
            ctx["field_name"] = field_name
        if field_value is not None:
            ctx["field_value"] = field_value
        super().__init__(
            message=message,
            error_code=error_code or ErrorCode.INVALID_FIELD_VALUE,
            severity=Severity.medium,
            context=ctx,
            original_error=original_error,
        )


class NegativeMetricError(CoreError):
    def __init__(
        self, field_name: str, field_value: Any, *, context: Optional[Dict[str, Any]] = None
    ) -> None:
        ctx = context.copy() if context else {}
        ctx.update({"field_name": field_name, "field_value": field_value})
        super().__init__(
            message=f"Negative value for metric '{field_name}': {field_value}",
            error_code=ErrorCode.NEGATIVE_METRIC_VALUE,
            severity=Severity.high,
            context=ctx,
        )


class ParserError(CoreError):
    def __init__(
        self,
        message: str,
        *,
        parser_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = context.copy() if context else {}
        if parser_name:
            ctx["parser_name"] = parser_name
        super().__init__(
            message=message,
            error_code=ErrorCode.PARSER_ERROR,
            severity=Severity.high,
            context=ctx,
        )


def to_core_error(exc: BaseException, *, default_category: str = "unknown") -> CoreError:
    """Convert an arbitrary exception to a CoreError with best-effort mapping.

    Known DSL exceptions are mapped to stable codes; otherwise falls back to
    a generic 'unhandled_exception' code with provided default_category.
    """
    for etype, meta in _DSL_EXCEPTION_MAP.items():
        if isinstance(exc, etype):
            # Map DSL exceptions to CoreError with legacy code/category preserved
            ce = CoreError(
                message=str(exc),
                error_code=ErrorCode.UNKNOWN_ERROR,
                severity=Severity.high,
                context={},
                original_error=exc,
                code=meta["code"],
                category=meta["category"],
            )
            return ce
    return CoreError(
        message=str(exc),
        error_code=ErrorCode.UNKNOWN_ERROR,
        severity=Severity.high,
        context={},
        original_error=exc,
        code="unhandled_exception",
        category=default_category,
    )


def wrap_exception(
    exception: BaseException,
    message: str,
    error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
    severity: Severity = Severity.medium,
    context: Optional[Dict[str, Any]] = None,
) -> CoreError:
    """Wrap an external exception in a CoreError with additional context."""
    return CoreError(
        message,
        error_code,
        severity,
        context=context,
        original_error=exception,
    )
