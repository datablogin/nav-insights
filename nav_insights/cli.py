#!/usr/bin/env python3
"""
CLI for nav-insights validation and utilities.

This module provides command-line tools for validating analyzer payloads,
managing schemas, and other nav-insights utilities.
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List

from jsonschema import Draft202012Validator


class ValidatorCLI:
    """CLI for validating analyzer payloads against JSON schemas."""

    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.schemas_path = self.base_path / "schemas"

    def get_available_types(self) -> List[str]:
        """Get list of available analyzer types for validation."""
        types = []

        # Check paid_search analyzers
        paid_search_path = self.schemas_path / "paid_search"
        if paid_search_path.exists():
            for schema_file in paid_search_path.glob("*.json"):
                # Convert filename to analyzer type (e.g., keyword_analyzer.json -> paid_search.keyword_analyzer)
                analyzer_name = schema_file.stem
                types.append(f"paid_search.{analyzer_name}")

        return sorted(types)

    def get_schema_path(self, analyzer_type: str) -> Path:
        """Get the schema file path for a given analyzer type."""
        if not analyzer_type.startswith("paid_search."):
            raise ValueError(
                f"Unsupported analyzer type: {analyzer_type}. Must start with 'paid_search.'"
            )

        analyzer_name = analyzer_type.replace("paid_search.", "")
        schema_path = self.schemas_path / "paid_search" / f"{analyzer_name}.json"

        if not schema_path.exists():
            raise ValueError(f"Schema not found for analyzer type: {analyzer_type}")

        return schema_path

    def load_schema(self, analyzer_type: str) -> Dict[str, Any]:
        """Load JSON schema for the given analyzer type."""
        schema_path = self.get_schema_path(analyzer_type)

        with open(schema_path, "r") as f:
            return json.load(f)

    def load_payload(self, input_path: str) -> Dict[str, Any]:
        """Load payload from file or stdin."""
        if input_path == "-":
            # Read from stdin
            try:
                return json.load(sys.stdin)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON from stdin: {e}")
        else:
            # Read from file
            file_path = Path(input_path)
            if not file_path.exists():
                raise ValueError(f"Input file not found: {input_path}")

            try:
                with open(file_path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in file {input_path}: {e}")

    def validate_payload(
        self, payload: Dict[str, Any], schema: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """Validate payload against schema. Returns (is_valid, error_messages)."""
        validator = Draft202012Validator(schema)
        errors = []

        for error in validator.iter_errors(payload):
            # Format error message nicely
            path = (
                " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
            )
            errors.append(f"At '{path}': {error.message}")

        return len(errors) == 0, errors

    def run_validate(self, analyzer_type: str, input_path: str, verbose: bool = False) -> int:
        """Run validation and return exit code."""
        try:
            # Load schema
            if verbose:
                print(f"Loading schema for: {analyzer_type}")
            schema = self.load_schema(analyzer_type)

            # Load payload
            if verbose:
                input_desc = "stdin" if input_path == "-" else input_path
                print(f"Loading payload from: {input_desc}")
            payload = self.load_payload(input_path)

            # Validate
            if verbose:
                print("Validating payload...")
            is_valid, errors = self.validate_payload(payload, schema)

            if is_valid:
                print("✅ Payload is valid")
                return 0
            else:
                print("❌ Payload validation failed:")
                for error in errors:
                    print(f"  • {error}")
                return 1

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    def list_types(self) -> int:
        """List available analyzer types."""
        types = self.get_available_types()

        if not types:
            print("No analyzer types available")
            return 1

        print("Available analyzer types:")
        for analyzer_type in types:
            print(f"  • {analyzer_type}")

        return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="nav-insights CLI for validation and utilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate a file
  nav-insights validate --type paid_search.keyword_analyzer --input data.json
  
  # Validate from stdin
  cat data.json | nav-insights validate --type paid_search.search_terms --input -
  
  # List available types
  nav-insights validate --list-types
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate analyzer payloads")
    validate_parser.add_argument(
        "--type", dest="analyzer_type", help="Analyzer type (e.g., paid_search.keyword_analyzer)"
    )
    validate_parser.add_argument(
        "--input",
        dest="input_path",
        default="-",
        help="Input file path or '-' for stdin (default: stdin)",
    )
    validate_parser.add_argument(
        "--list-types", action="store_true", help="List available analyzer types"
    )
    validate_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    cli = ValidatorCLI()

    if args.command == "validate":
        if args.list_types:
            return cli.list_types()

        if not args.analyzer_type:
            print("Error: --type is required", file=sys.stderr)
            validate_parser.print_help()
            return 1

        return cli.run_validate(args.analyzer_type, args.input_path, args.verbose)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
