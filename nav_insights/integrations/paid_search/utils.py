"""Shared utilities for PaidSearch integration parsers."""

from typing import Any

from ...core.ir_base import Severity


def map_priority_level(level: Any) -> Severity:
    """Map PaidSearchNav priority levels to Core IR Severity values.

    Args:
        level: Priority level string from PaidSearchNav (CRITICAL, HIGH, MEDIUM, LOW, etc.)

    Returns:
        Corresponding Severity enum value
    """
    s = str(level or "").lower()
    if s in ("critical", "high"):
        return Severity.high
    if s == "medium":
        return Severity.medium
    return Severity.low
