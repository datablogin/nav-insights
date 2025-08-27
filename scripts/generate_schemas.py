#!/usr/bin/env python3
"""
Generate JSON schemas for analyzer input payloads.

This script extracts JSON schemas from pydantic models and saves them
to the schemas/ directory for validation purposes.
"""

import json
from pathlib import Path

# Import all analyzer input models
from nav_insights.integrations.paid_search.keyword_analyzer import KeywordAnalyzerInput
from nav_insights.integrations.paid_search.search_terms import SearchTermsInput
from nav_insights.integrations.paid_search.competitor_insights import CompetitorInsightsInput
from nav_insights.integrations.paid_search.placement_audit import PlacementAuditInput
from nav_insights.integrations.paid_search.video_creative import VideoCreativeInput


def generate_schema(model_class, output_path: Path) -> None:
    """Generate JSON schema for a pydantic model and save to file."""
    schema = model_class.model_json_schema()

    # Add metadata
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = f"{model_class.__name__} Schema"
    schema["description"] = f"JSON schema for {model_class.__name__} payload validation"

    # Create directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write schema to file
    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2, sort_keys=True)

    print(f"Generated schema: {output_path}")


def main():
    """Generate all analyzer payload schemas."""
    base_path = Path(__file__).parent.parent / "schemas" / "paid_search"

    # Define models and their output filenames
    models = {
        KeywordAnalyzerInput: "keyword_analyzer.json",
        SearchTermsInput: "search_terms.json",
        CompetitorInsightsInput: "competitor_insights.json",
        PlacementAuditInput: "placement_audit.json",
        VideoCreativeInput: "video_creative.json",
    }

    for model_class, filename in models.items():
        output_path = base_path / filename
        try:
            generate_schema(model_class, output_path)
        except Exception as e:
            print(f"Error generating schema for {model_class.__name__}: {e}")

    print(f"\nSchemas generated in: {base_path}")


if __name__ == "__main__":
    main()
