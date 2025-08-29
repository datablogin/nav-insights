"""Core utilities for nav_insights engine.

This module provides shared utilities for all parsers and analyzers:
- Severity/priority mapping
- Finding ID generation with uniqueness guarantees
- Metric validation
"""

from __future__ import annotations
import hashlib
import decimal
from decimal import Decimal
from typing import Any, Dict, List

from .ir_base import Severity
from .errors import NegativeMetricError, ValidationError, ErrorCode


def map_priority_level(level: Any) -> Severity:
    """Map priority level string to Severity enum.

    This is the single source of truth for severity mapping across all parsers.

    Args:
        level: Priority level from external data (string, None, etc.)

    Returns:
        Severity: Mapped severity level

    Examples:
        >>> map_priority_level("CRITICAL")
        Severity.high
        >>> map_priority_level("high")
        Severity.high
        >>> map_priority_level("medium")
        Severity.medium
        >>> map_priority_level(None)
        Severity.low
    """
    if level is None:
        return Severity.low

    level_str = str(level).lower().strip()

    if level_str in ("critical", "high"):
        return Severity.high
    elif level_str == "medium":
        return Severity.medium
    else:
        return Severity.low


def generate_finding_id(base_id: str, *entity_parts: str) -> str:
    """Generate a unique finding ID with deterministic hashing.

    Creates a stable, unique ID by combining a base identifier with entity-specific
    parts and adding a hash suffix to prevent collisions.

    Format guarantees:
    - All parts converted to UPPERCASE with underscores as separators
    - Special characters sanitized to underscores
    - 8-character hexadecimal hash suffix for collision prevention
    - Format: "BASE_ID_ENTITY1_ENTITY2_12345678"

    Args:
        base_id: Base identifier (e.g., "KW_UNDER", "COMPETITOR")
        *entity_parts: Variable entity identifiers (name, campaign, etc.)

    Returns:
        str: Unique finding ID with format "SANITIZED_PARTS_HASH8"

    Examples:
        >>> generate_finding_id("KW_UNDER", "food delivery", "BROAD")
        'KW_UNDER_FOOD_DELIVERY_BROAD_a1b2c3d4'
        >>> generate_finding_id("COMPETITOR", "Cracker Barrel")
        'COMPETITOR_CRACKER_BARREL_e5f6g7h8'
    """
    if not base_id:
        raise ValidationError(
            "Base ID cannot be empty",
            field_name="base_id",
            field_value=base_id,
        )

    # Sanitize and combine all parts
    sanitized_parts = [_sanitize_id_part(str(part)) for part in [base_id] + list(entity_parts)]
    combined = "_".join(part for part in sanitized_parts if part)

    # Create deterministic hash from all parts
    hash_input = "|".join(str(part) for part in [base_id] + list(entity_parts))
    hash_suffix = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:8]

    return f"{combined}_{hash_suffix}"


def _sanitize_id_part(part: str) -> str:
    """Sanitize a string for use in finding IDs."""
    if not part:
        return ""

    # Replace problematic characters with underscores
    sanitized = "".join(char if char.isalnum() else "_" for char in part.upper())

    # Remove consecutive underscores and trim
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")

    return sanitized.strip("_")


def validate_non_negative_metrics(
    metrics: Dict[str, Any],
    metric_names: List[str],
    parser_name: str = "unknown",
) -> Dict[str, Decimal]:
    """Validate that specified metrics are non-negative and convert to Decimal.

    Only returns metrics that are present, non-empty, and convertible to Decimal.
    Missing, None, or "N/A" values are silently skipped. Callers should merge
    the result into their metrics dictionary as needed.

    Args:
        metrics: Dictionary of metric name to value
        metric_names: List of metric names that must be non-negative
        parser_name: Name of parser for error context

    Returns:
        Dict[str, Decimal]: Validated and converted metrics (subset of input)

    Raises:
        NegativeMetricError: If any specified metric is negative
        ValidationError: If metric conversion fails
    """
    validated_metrics: Dict[str, Decimal] = {}

    for metric_name in metric_names:
        if metric_name not in metrics:
            continue

        value = metrics[metric_name]

        # Skip None values or "N/A" strings
        if value is None or value == "N/A":
            continue

        # Convert to Decimal
        try:
            decimal_value = Decimal(str(value))
        except (ValueError, TypeError, decimal.InvalidOperation) as e:
            raise ValidationError(
                f"Cannot convert metric '{metric_name}' to decimal: {value}",
                field_name=metric_name,
                field_value=value,
                context={"parser_name": parser_name},
                original_error=e,
            )

        # Check for negative values
        if decimal_value < 0:
            raise NegativeMetricError(
                field_name=metric_name,
                field_value=decimal_value,
                context={"parser_name": parser_name},
            )

        validated_metrics[metric_name] = decimal_value

    return validated_metrics


def safe_decimal_conversion(
    value: Any, field_name: str, default: Decimal = Decimal("0")
) -> Decimal:
    """Safely convert a value to Decimal with fallback.

    Args:
        value: Value to convert
        field_name: Name of field for error reporting
        default: Default value if conversion fails or value is None/"N/A"

    Returns:
        Decimal: Converted value or default

    Raises:
        ValidationError: If conversion fails for non-None, non-"N/A" values
    """
    if value is None or value == "N/A":
        return default

    try:
        return Decimal(str(value))
    except (ValueError, TypeError, decimal.InvalidOperation) as e:
        raise ValidationError(
            f"Cannot convert '{field_name}' to decimal: {value}",
            field_name=field_name,
            field_value=value,
            original_error=e,
        )


def validate_required_fields(
    data: Dict[str, Any], required_fields: List[str], parser_name: str = "unknown"
) -> None:
    """Validate that required fields are present and not None.

    Args:
        data: Data dictionary to validate
        required_fields: List of required field names
        parser_name: Name of parser for error context

    Raises:
        ValidationError: If any required field is missing or None
    """
    missing_fields = []

    for field_name in required_fields:
        if field_name not in data or data[field_name] is None:
            missing_fields.append(field_name)

    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {missing_fields}",
            context={
                "parser_name": parser_name,
                "missing_fields": missing_fields,
                "available_fields": list(data.keys()),
            },
            error_code=ErrorCode.MISSING_REQUIRED_FIELD,
        )
