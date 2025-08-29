#!/usr/bin/env python3
"""
Validate all analyzer fixtures against their schemas.

This script validates test fixtures in tests/fixtures/ against their
corresponding JSON schemas to ensure they remain valid as schemas evolve.
"""

import sys
from pathlib import Path
from typing import List, Tuple

from nav_insights.cli import ValidatorCLI


def map_fixture_to_analyzer_type(fixture_path: Path) -> str:
    """Map fixture filename to analyzer type."""
    filename = fixture_path.stem

    # Remove common suffixes
    filename = filename.replace("_happy_path", "").replace("_edge_case", "")

    # Map fixture patterns to analyzer types
    mapping = {
        "keyword_analyzer": "paid_search.keyword_analyzer",
        "search_terms": "paid_search.search_terms",
        "competitor_insights": "paid_search.competitor_insights",
        "placement_audit": "paid_search.placement_audit",
        "video_creative": "paid_search.video_creative",
        # Add patterns for other fixture types that don't follow exact naming
        "negative_conflicts_fixture": "paid_search.search_terms",  # These are search_terms fixtures
    }

    for pattern, analyzer_type in mapping.items():
        if pattern in filename:
            return analyzer_type

    return None


def get_fixtures_to_validate() -> List[Tuple[Path, str]]:
    """Get list of (fixture_path, analyzer_type) tuples for validation."""
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"

    if not fixtures_dir.exists():
        return []

    # Configurable skip patterns for IR fixtures (not analyzer inputs)
    # These patterns indicate files that represent IR output, not analyzer input
    ir_fixture_patterns = [
        "_fixture",  # Files ending in _fixture (e.g., negative_conflicts_fixture.json)
        "search_fixture",  # Search IR fixtures
        "social_fixture",  # Social IR fixtures
        "negative_conflicts",  # Legacy negative conflicts IR
    ]

    fixtures = []

    for fixture_file in fixtures_dir.glob("*.json"):
        # Skip IR fixture files (these are not analyzer inputs)
        # Special handling: files with _fixture in the name are IR fixtures even if they
        # have _happy_path or _edge_case suffixes
        is_ir_fixture = any(pattern in fixture_file.name for pattern in ir_fixture_patterns)

        if is_ir_fixture:
            continue

        analyzer_type = map_fixture_to_analyzer_type(fixture_file)
        if analyzer_type:
            fixtures.append((fixture_file, analyzer_type))
        else:
            print(f"⚠️  Could not map fixture to analyzer type: {fixture_file.name}")

    return fixtures


def validate_fixtures() -> int:
    """Validate all fixtures and return exit code."""
    fixtures = get_fixtures_to_validate()

    if not fixtures:
        print("No fixtures found to validate")
        return 0

    cli = ValidatorCLI()
    results = []

    print(f"🧪 Validating {len(fixtures)} analyzer fixtures...\n")

    for fixture_path, analyzer_type in fixtures:
        print(f"Validating {fixture_path.name} as {analyzer_type}...")

        try:
            # Load schema and payload
            schema = cli.load_schema(analyzer_type)
            payload = cli.load_payload(str(fixture_path))

            # Validate
            is_valid, errors = cli.validate_payload(payload, schema)

            if is_valid:
                print("  ✅ Valid")
                results.append(True)
            else:
                print("  ❌ Invalid:")
                for error in errors:
                    print(f"    • {error}")
                results.append(False)

        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append(False)

        print()

    # Summary
    passed = sum(results)
    total = len(results)
    failed = total - passed

    print("=" * 50)
    print("FIXTURE VALIDATION RESULTS")
    print("=" * 50)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {total}")

    if failed == 0:
        print("\n🎉 All fixtures are valid!")
        return 0
    else:
        print(f"\n💥 {failed} fixture(s) failed validation")
        return 1


if __name__ == "__main__":
    sys.exit(validate_fixtures())
