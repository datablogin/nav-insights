"""Tests for core utilities and error handling."""

import pytest
from decimal import Decimal
from nav_insights.core import (
    CoreError,
    ValidationError,
    ParserError,
    NegativeMetricError,
    ErrorCode,
    map_priority_level,
    generate_finding_id,
    validate_non_negative_metrics,
    safe_decimal_conversion,
    validate_required_fields,
    wrap_exception,
)
from nav_insights.core.ir_base import Severity


class TestErrorTaxonomy:
    """Test the unified error taxonomy."""

    def test_core_error_basic(self):
        """Test basic CoreError functionality."""
        error = CoreError("Test message", ErrorCode.INVALID_INPUT_DATA, Severity.high)
        assert error.message == "Test message"
        assert error.error_code == ErrorCode.INVALID_INPUT_DATA
        assert error.severity == Severity.high
        assert error.context == {}
        assert error.original_error is None

    def test_core_error_with_context(self):
        """Test CoreError with additional context."""
        context = {"field": "test", "value": 123}
        error = CoreError(
            "Test message",
            ErrorCode.INVALID_FIELD_VALUE,
            Severity.medium,
            context=context,
        )
        assert error.context == context

    def test_core_error_with_original_error(self):
        """Test CoreError wrapping original exception."""
        original = ValueError("Original error")
        error = CoreError("Wrapped error", original_error=original)
        assert error.original_error == original
        assert "Original: Original error" in str(error)

    def test_validation_error(self):
        """Test ValidationError specialization."""
        error = ValidationError("Invalid value", field_name="cost", field_value=-10)
        assert error.error_code == ErrorCode.INVALID_FIELD_VALUE
        assert error.context["field_name"] == "cost"
        assert error.context["field_value"] == -10

    def test_parser_error(self):
        """Test ParserError specialization."""
        error = ParserError("Parse failed", parser_name="KeywordAnalyzer")
        assert error.error_code == ErrorCode.PARSER_ERROR
        assert error.context["parser_name"] == "KeywordAnalyzer"

    def test_negative_metric_error(self):
        """Test NegativeMetricError specialization."""
        error = NegativeMetricError("cost", -50.0)
        assert error.error_code == ErrorCode.NEGATIVE_METRIC_VALUE
        assert error.context["field_name"] == "cost"
        assert error.context["field_value"] == -50.0
        assert "cost" in error.message
        assert "-50.0" in error.message

    def test_wrap_exception(self):
        """Test exception wrapping utility."""
        original = ValueError("Original error")
        wrapped = wrap_exception(
            original,
            "Wrapped message",
            ErrorCode.PARSER_ERROR,
            Severity.high,
            {"key": "value"},
        )
        assert isinstance(wrapped, CoreError)
        assert wrapped.message == "Wrapped message"
        assert wrapped.error_code == ErrorCode.PARSER_ERROR
        assert wrapped.severity == Severity.high
        assert wrapped.context == {"key": "value"}
        assert wrapped.original_error == original


class TestSeverityMapping:
    """Test the unified severity mapping function."""

    def test_map_priority_level_high_values(self):
        """Test mapping of high priority values."""
        assert map_priority_level("CRITICAL") == Severity.high
        assert map_priority_level("critical") == Severity.high
        assert map_priority_level("HIGH") == Severity.high
        assert map_priority_level("high") == Severity.high
        assert map_priority_level("High") == Severity.high

    def test_map_priority_level_medium_values(self):
        """Test mapping of medium priority values."""
        assert map_priority_level("MEDIUM") == Severity.medium
        assert map_priority_level("medium") == Severity.medium
        assert map_priority_level("Medium") == Severity.medium

    def test_map_priority_level_low_values(self):
        """Test mapping of low priority values."""
        assert map_priority_level("LOW") == Severity.low
        assert map_priority_level("low") == Severity.low
        assert map_priority_level("unknown") == Severity.low
        assert map_priority_level("invalid") == Severity.low
        assert map_priority_level("") == Severity.low
        assert map_priority_level("   ") == Severity.low

    def test_map_priority_level_none_values(self):
        """Test mapping of None and null values."""
        assert map_priority_level(None) == Severity.low
        assert map_priority_level(0) == Severity.low
        assert map_priority_level(False) == Severity.low


class TestFindingIdGeneration:
    """Test the finding ID generation utilities."""

    def test_generate_finding_id_basic(self):
        """Test basic ID generation."""
        finding_id = generate_finding_id("TEST", "entity1")
        assert finding_id.startswith("TEST_ENTITY1_")
        parts = finding_id.split("_")
        assert len(parts) == 3
        assert len(parts[-1]) == 8  # Hash suffix

    def test_generate_finding_id_multiple_parts(self):
        """Test ID generation with multiple entity parts."""
        finding_id = generate_finding_id("KW_UNDER", "food delivery", "BROAD")
        assert finding_id.startswith("KW_UNDER_FOOD_DELIVERY_BROAD_")
        parts = finding_id.split("_")
        # KW_UNDER becomes KW and UNDER, food_delivery becomes FOOD and DELIVERY, BROAD, plus hash
        assert len(parts) == 6
        assert len(parts[-1]) == 8

    def test_generate_finding_id_special_characters(self):
        """Test ID generation with special characters."""
        finding_id = generate_finding_id("TEST", "entity with spaces!", "type@#$")
        # Should sanitize special characters to underscores
        assert "ENTITY_WITH_SPACES" in finding_id
        assert "TYPE" in finding_id
        assert "!" not in finding_id
        assert "@" not in finding_id

    def test_generate_finding_id_deterministic(self):
        """Test that ID generation is deterministic."""
        id1 = generate_finding_id("TEST", "entity", "type")
        id2 = generate_finding_id("TEST", "entity", "type")
        assert id1 == id2

    def test_generate_finding_id_unique_for_different_inputs(self):
        """Test that different inputs produce different IDs."""
        id1 = generate_finding_id("TEST", "entity1", "type")
        id2 = generate_finding_id("TEST", "entity2", "type")
        assert id1 != id2

    def test_generate_finding_id_empty_base_id_error(self):
        """Test that empty base ID raises error."""
        with pytest.raises(ValidationError) as exc_info:
            generate_finding_id("", "entity")
        assert "Base ID cannot be empty" in str(exc_info.value)


class TestMetricValidation:
    """Test metric validation utilities."""

    def test_validate_non_negative_metrics_valid(self):
        """Test validation with valid metrics."""
        metrics = {"cost": 100.50, "conversions": 5, "clicks": 200}
        result = validate_non_negative_metrics(
            metrics, ["cost", "conversions", "clicks"], "TestParser"
        )
        assert result["cost"] == Decimal("100.50")
        assert result["conversions"] == Decimal("5")
        assert result["clicks"] == Decimal("200")

    def test_validate_non_negative_metrics_negative_value(self):
        """Test validation with negative metric."""
        metrics = {"cost": -50.0, "conversions": 5}
        with pytest.raises(NegativeMetricError) as exc_info:
            validate_non_negative_metrics(metrics, ["cost"], "TestParser")
        assert "cost" in str(exc_info.value)
        assert "-50" in str(exc_info.value)

    def test_validate_non_negative_metrics_missing_metric(self):
        """Test validation with missing metric (should be skipped)."""
        metrics = {"conversions": 5}
        result = validate_non_negative_metrics(metrics, ["cost", "conversions"], "TestParser")
        assert "cost" not in result
        assert result["conversions"] == Decimal("5")

    def test_validate_non_negative_metrics_none_value(self):
        """Test validation with None value (should be skipped)."""
        metrics = {"cost": None, "conversions": 5}
        result = validate_non_negative_metrics(metrics, ["cost", "conversions"], "TestParser")
        assert "cost" not in result
        assert result["conversions"] == Decimal("5")

    def test_validate_non_negative_metrics_na_value(self):
        """Test validation with 'N/A' value (should be skipped)."""
        metrics = {"cost": "N/A", "conversions": 5}
        result = validate_non_negative_metrics(metrics, ["cost", "conversions"], "TestParser")
        assert "cost" not in result
        assert result["conversions"] == Decimal("5")

    def test_validate_non_negative_metrics_invalid_conversion(self):
        """Test validation with value that can't be converted to decimal."""
        metrics = {"cost": "invalid", "conversions": 5}
        with pytest.raises(ValidationError) as exc_info:
            validate_non_negative_metrics(metrics, ["cost"], "TestParser")
        assert "Cannot convert metric 'cost' to decimal" in str(exc_info.value)

    def test_safe_decimal_conversion_valid(self):
        """Test safe decimal conversion with valid values."""
        assert safe_decimal_conversion(100, "cost") == Decimal("100")
        assert safe_decimal_conversion("50.25", "amount") == Decimal("50.25")
        assert safe_decimal_conversion(0, "zero") == Decimal("0")

    def test_safe_decimal_conversion_none(self):
        """Test safe decimal conversion with None."""
        assert safe_decimal_conversion(None, "cost") == Decimal("0")
        assert safe_decimal_conversion(None, "cost", Decimal("999")) == Decimal("999")

    def test_safe_decimal_conversion_na(self):
        """Test safe decimal conversion with 'N/A'."""
        assert safe_decimal_conversion("N/A", "cost") == Decimal("0")
        assert safe_decimal_conversion("N/A", "cost", Decimal("123")) == Decimal("123")

    def test_safe_decimal_conversion_invalid(self):
        """Test safe decimal conversion with invalid value."""
        with pytest.raises(ValidationError) as exc_info:
            safe_decimal_conversion("invalid", "cost")
        assert "Cannot convert 'cost' to decimal" in str(exc_info.value)

    def test_validate_required_fields_all_present(self):
        """Test required field validation with all fields present."""
        data = {"field1": "value1", "field2": "value2", "field3": "value3"}
        # Should not raise
        validate_required_fields(data, ["field1", "field2"], "TestParser")

    def test_validate_required_fields_missing_field(self):
        """Test required field validation with missing field."""
        data = {"field1": "value1"}
        with pytest.raises(ValidationError) as exc_info:
            validate_required_fields(data, ["field1", "field2"], "TestParser")
        assert "Missing required fields: ['field2']" in str(exc_info.value)
        assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD

    def test_validate_required_fields_none_value(self):
        """Test required field validation with None value."""
        data = {"field1": "value1", "field2": None}
        with pytest.raises(ValidationError) as exc_info:
            validate_required_fields(data, ["field1", "field2"], "TestParser")
        assert "Missing required fields: ['field2']" in str(exc_info.value)

    def test_validate_required_fields_multiple_missing(self):
        """Test required field validation with multiple missing fields."""
        data = {"field1": "value1"}
        with pytest.raises(ValidationError) as exc_info:
            validate_required_fields(data, ["field1", "field2", "field3"], "TestParser")
        assert "field2" in str(exc_info.value)
        assert "field3" in str(exc_info.value)
