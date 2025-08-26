from __future__ import annotations
from typing import Any, Dict, Optional, Type

from . import dsl_exceptions as dslx


class CoreError(Exception):
    """Structured error used across core and integrations.

    Attributes:
        code: Stable machine-readable code (e.g., 'resource_limit', 'invalid_metric')
        category: High-level subsystem (e.g., 'dsl', 'parser.keyword', 'service')
        severity: One of {'info','warning','error','critical'}
        message: Human-readable message
        context: Optional structured context payload safe to log/serialize
    """

    def __init__(
        self,
        code: str,
        category: str,
        message: str,
        *,
        severity: str = "error",
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.category = category
        self.severity = severity
        self.message = message
        self.context = context or {}
        self.cause = cause

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "context": self.context,
        }
        if self.cause is not None:
            data["cause"] = type(self.cause).__name__
        return data

    def __str__(self) -> str:  # pragma: no cover - convenience
        return f"[{self.category}:{self.code}] {self.message}"


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
    """
    for etype, meta in _DSL_EXCEPTION_MAP.items():
        if isinstance(exc, etype):
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
