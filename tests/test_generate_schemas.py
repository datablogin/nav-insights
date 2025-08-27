"""Tests for the schema generation script."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch


from scripts.generate_schemas import generate_schema, main


class TestSchemaGeneration:
    """Test cases for schema generation functionality."""

    def test_generate_schema(self):
        """Test generating schema for a model class."""

        # Mock a simple pydantic model
        class MockModel:
            @classmethod
            def model_json_schema(cls):
                return {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
                }

            __name__ = "MockModel"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_schema.json"

            with patch("builtins.print"):
                generate_schema(MockModel, output_path)

            # Check file was created
            assert output_path.exists()

            # Check content
            with open(output_path) as f:
                schema = json.load(f)

            assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
            assert schema["title"] == "MockModel Schema"
            assert schema["type"] == "object"
            assert "properties" in schema

    def test_generate_schema_creates_directory(self):
        """Test that generate_schema creates directories if they don't exist."""

        class MockModel:
            @classmethod
            def model_json_schema(cls):
                return {"type": "object", "properties": {}}

            __name__ = "MockModel"

        with tempfile.TemporaryDirectory() as temp_dir:
            # Path with nested directories that don't exist
            output_path = Path(temp_dir) / "nested" / "path" / "schema.json"

            with patch("builtins.print"):
                generate_schema(MockModel, output_path)

            # Check file was created and directories exist
            assert output_path.exists()
            assert output_path.parent.is_dir()

    @patch("builtins.print")
    @patch("scripts.generate_schemas.generate_schema")
    def test_main_function(self, mock_generate, mock_print):
        """Test the main function calls generate_schema for all models."""
        main()

        # Should have been called for each model
        assert mock_generate.call_count == 5

        # Check that it was called with expected model classes
        call_args = [call[0][0] for call in mock_generate.call_args_list]
        model_names = [cls.__name__ for cls in call_args]

        expected_names = [
            "KeywordAnalyzerInput",
            "SearchTermsInput",
            "CompetitorInsightsInput",
            "PlacementAuditInput",
            "VideoCreativeInput",
        ]

        for expected in expected_names:
            assert expected in model_names

    @patch("builtins.print")
    @patch("scripts.generate_schemas.generate_schema")
    def test_main_handles_exceptions(self, mock_generate, mock_print):
        """Test that main handles exceptions gracefully."""
        # Make generate_schema raise an exception
        mock_generate.side_effect = Exception("Test error")

        # Should not raise, just print error
        main()

        # Should have tried to generate all schemas
        assert mock_generate.call_count == 5

    def test_model_imports(self):
        """Test that all required models can be imported."""
        # This tests the actual imports in the script
        from nav_insights.integrations.paid_search.keyword_analyzer import KeywordAnalyzerInput
        from nav_insights.integrations.paid_search.search_terms import SearchTermsInput
        from nav_insights.integrations.paid_search.competitor_insights import (
            CompetitorInsightsInput,
        )
        from nav_insights.integrations.paid_search.placement_audit import PlacementAuditInput
        from nav_insights.integrations.paid_search.video_creative import VideoCreativeInput

        models = [
            KeywordAnalyzerInput,
            SearchTermsInput,
            CompetitorInsightsInput,
            PlacementAuditInput,
            VideoCreativeInput,
        ]

        for model_class in models:
            # Should be able to get the schema
            schema = model_class.model_json_schema()
            assert isinstance(schema, dict)
            assert "type" in schema

            # Should have a recognizable class name
            assert hasattr(model_class, "__name__")
            assert model_class.__name__.endswith("Input")

    def test_schema_generation_integration(self):
        """Integration test: generate actual schemas and validate structure."""
        from nav_insights.integrations.paid_search.keyword_analyzer import KeywordAnalyzerInput

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "keyword_analyzer.json"

            with patch("builtins.print"):
                generate_schema(KeywordAnalyzerInput, output_path)

            # Load and validate the generated schema
            with open(output_path) as f:
                schema = json.load(f)

            # Basic schema structure checks
            assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
            assert schema["title"] == "KeywordAnalyzerInput Schema"
            assert schema["type"] == "object"
            assert "properties" in schema

            # Should be valid JSON
            json_str = json.dumps(schema)
            parsed = json.loads(json_str)
            assert parsed == schema
