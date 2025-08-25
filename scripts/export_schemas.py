#!/usr/bin/env python3
"""
JSON Schema Export CLI

Exports JSON schemas for all core IR models to docs/schemas/ directory.
This addresses ChatGPT's recommendation for schema delivery.
"""

import json
from pathlib import Path
from nav_insights.core.findings_ir import export_all_schemas


def main():
    """Export all schemas to docs/schemas/ directory."""
    # Create output directory
    output_dir = Path("docs/schemas")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Export all schemas
    schemas = export_all_schemas()

    print(f"Exporting {len(schemas)} schemas to {output_dir}/")

    for name, schema in schemas.items():
        output_file = output_dir / f"{name}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2, sort_keys=True)
        print(f"  ✓ {name}.json")

    print(f"\nSuccessfully exported {len(schemas)} JSON schemas!")
    print("Files created:")
    for name in sorted(schemas.keys()):
        print(f"  - docs/schemas/{name}.json")


if __name__ == "__main__":
    main()
