"""Core utilities and error handling for nav_insights."""

from .errors import (
    CoreError,
    ValidationError,
    ParserError,
    NegativeMetricError,
    ErrorCode,
    wrap_exception,
    to_core_error,
)
from .utils import (
    map_priority_level,
    generate_finding_id,
    validate_non_negative_metrics,
    safe_decimal_conversion,
    validate_required_fields,
)

__all__ = [
    # Error classes
    "CoreError",
    "ValidationError",
    "ParserError",
    "NegativeMetricError",
    "ErrorCode",
    "wrap_exception",
    "to_core_error",
    # Utility functions
    "map_priority_level",
    "generate_finding_id",
    "validate_non_negative_metrics",
    "safe_decimal_conversion",
    "validate_required_fields",
]