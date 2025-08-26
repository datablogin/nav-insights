"""Tests for the CLI validation functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from nav_insights.cli import ValidatorCLI


class TestValidatorCLI:
    """Test cases for ValidatorCLI."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = ValidatorCLI()

    def test_get_available_types(self):
        """Test listing available analyzer types."""
        types = self.cli.get_available_types()

        # Should include paid search types
        assert "paid_search.keyword_analyzer" in types
        assert "paid_search.search_terms" in types
        assert "paid_search.competitor_insights" in types
        assert "paid_search.placement_audit" in types
        assert "paid_search.video_creative" in types

        # Should be sorted
        assert types == sorted(types)

    def test_load_schema_valid_type(self):
        """Test loading a valid schema."""
        schema = self.cli.load_schema("paid_search.keyword_analyzer")

        # Should be a valid JSON schema
        assert isinstance(schema, dict)
        assert "$schema" in schema
        assert "type" in schema
        assert schema["type"] == "object"

    def test_load_schema_invalid_type(self):
        """Test loading an invalid schema type."""
        with pytest.raises(ValueError, match="Unsupported domain"):
            self.cli.load_schema("invalid.type")

    def test_load_payload_valid_file(self):
        """Test loading a valid JSON payload file."""
        test_payload = {"test": "data"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(test_payload, f)
            temp_path = f.name

        try:
            payload = self.cli.load_payload(temp_path)
            assert payload == test_payload
        finally:
            Path(temp_path).unlink()

    def test_load_payload_stdin(self):
        """Test loading payload from stdin."""
        test_payload = {"test": "data"}
        test_json = json.dumps(test_payload)

        from io import StringIO

        with patch("sys.stdin", StringIO(test_json)):
            payload = self.cli.load_payload("-")
            assert payload == test_payload

    def test_load_payload_invalid_json(self):
        """Test loading invalid JSON payload."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                self.cli.load_payload(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_load_payload_nonexistent_file(self):
        """Test loading from nonexistent file."""
        with pytest.raises(ValueError, match="Input file not found"):
            self.cli.load_payload("/path/that/does/not/exist.json")

    def test_validate_payload_valid(self):
        """Test validating a valid payload."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
            "required": ["name"],
        }

        payload = {"name": "test", "age": 25}

        is_valid, errors = self.cli.validate_payload(payload, schema)
        assert is_valid is True
        assert errors == []

    def test_validate_payload_invalid(self):
        """Test validating an invalid payload."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
            "required": ["name", "age"],
        }

        payload = {"name": "test"}  # Missing required 'age'

        is_valid, errors = self.cli.validate_payload(payload, schema)
        assert is_valid is False
        assert len(errors) == 1
        assert "age" in errors[0]
        assert "required" in errors[0].lower()

    def test_validate_payload_type_mismatch(self):
        """Test validation with type mismatch."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
        }

        payload = {"name": "test", "age": "not a number"}

        is_valid, errors = self.cli.validate_payload(payload, schema)
        assert is_valid is False
        assert len(errors) == 1
        assert "age" in errors[0]

    def test_validate_payload_nested_object(self):
        """Test validation with nested object errors."""
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                }
            },
        }

        payload = {"user": {}}  # Missing required 'name'

        is_valid, errors = self.cli.validate_payload(payload, schema)
        assert is_valid is False
        assert len(errors) == 1
        assert "user -> name" in errors[0] or "user" in errors[0]

    @patch("nav_insights.cli.ValidatorCLI.get_available_types")
    def test_main_list_types(self, mock_get_types):
        """Test main function with --list-types."""
        from nav_insights.cli import main

        mock_get_types.return_value = ["type1", "type2"]

        with patch("sys.argv", ["nav-insights", "validate", "--list-types"]):
            with patch("builtins.print") as mock_print:
                result = main()

                assert result == 0
                mock_print.assert_called()

    @patch("nav_insights.cli.ValidatorCLI.load_schema")
    @patch("nav_insights.cli.ValidatorCLI.load_payload")
    @patch("nav_insights.cli.ValidatorCLI.validate_payload")
    def test_main_validate_success(self, mock_validate, mock_load_payload, mock_load_schema):
        """Test main function with successful validation."""
        from nav_insights.cli import main

        mock_load_schema.return_value = {"type": "object"}
        mock_load_payload.return_value = {"test": "data"}
        mock_validate.return_value = (True, [])

        with patch(
            "sys.argv", ["nav-insights", "validate", "--type", "test.type", "--input", "test.json"]
        ):
            with patch("builtins.print") as mock_print:
                result = main()

                assert result == 0
                mock_print.assert_called_with("✅ Payload is valid")

    @patch("nav_insights.cli.ValidatorCLI.load_schema")
    @patch("nav_insights.cli.ValidatorCLI.load_payload")
    @patch("nav_insights.cli.ValidatorCLI.validate_payload")
    def test_main_validate_failure(self, mock_validate, mock_load_payload, mock_load_schema):
        """Test main function with validation failure."""
        from nav_insights.cli import main

        mock_load_schema.return_value = {"type": "object"}
        mock_load_payload.return_value = {"test": "data"}
        mock_validate.return_value = (False, ["Error 1", "Error 2"])

        with patch(
            "sys.argv", ["nav-insights", "validate", "--type", "test.type", "--input", "test.json"]
        ):
            with patch("builtins.print") as mock_print:
                result = main()

                assert result == 1
                mock_print.assert_any_call("❌ Payload validation failed:")

    def test_main_missing_required_args(self):
        """Test main function with missing required arguments."""
        from nav_insights.cli import main

        with patch("sys.argv", ["nav-insights", "validate"]):
            with patch("builtins.print"):
                result = main()

                # Returns 1 for missing args
                assert result == 1

    def test_get_supported_domains(self):
        """Test getting supported domains."""
        domains = self.cli.get_supported_domains()

        # Should include paid_search
        assert "paid_search" in domains

        # Should be sorted
        assert domains == sorted(domains)

    def test_schema_caching(self):
        """Test that schemas are cached for performance."""
        analyzer_type = "paid_search.keyword_analyzer"

        # Load schema twice
        schema1 = self.cli.load_schema(analyzer_type)
        schema2 = self.cli.load_schema(analyzer_type)

        # Should be the same object (cached)
        assert schema1 is schema2

        # Should be in cache
        assert analyzer_type in self.cli._schema_cache

    def test_validate_schema_itself(self):
        """Test schema self-validation."""
        # Valid schema
        valid_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }

        assert self.cli.validate_schema_itself(valid_schema) is True

        # Invalid schema (missing required properties)
        invalid_schema = {"type": "invalid_type"}

        assert self.cli.validate_schema_itself(invalid_schema) is False

    def test_error_path_formatting_with_arrays(self):
        """Test that array indices are formatted nicely in error paths."""
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                }
            },
        }

        # Payload with invalid array item
        payload = {
            "items": [
                {"name": "valid"},
                {"invalid": "missing name"},  # Missing required 'name'
            ]
        }

        is_valid, errors = self.cli.validate_payload(payload, schema)
        assert is_valid is False
        assert len(errors) == 1
        # Should format array index nicely
        assert "items -> [1]" in errors[0]

    def test_invalid_format_analyzer_type(self):
        """Test error for invalid analyzer type format."""
        with pytest.raises(ValueError, match="Invalid analyzer type format"):
            self.cli.load_schema("invalid_format_no_dot")
