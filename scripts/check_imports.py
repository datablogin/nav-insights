#!/usr/bin/env python3
"""
Static analyzer to enforce core/domain boundaries.

This script prevents imports from domains/* or integrations/* in core modules
to maintain the engine's reusability.
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple


class ImportViolationChecker(ast.NodeVisitor):
    """AST visitor to check for forbidden imports in core modules."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.violations: List[Tuple[int, str]] = []
        self.forbidden_patterns = [
            "nav_insights.domains",
            "nav_insights.integrations",
            ".domains",
            ".integrations",
        ]

    def _is_forbidden_import(self, module_name: str) -> bool:
        """Check if a module name matches forbidden patterns."""
        return any(
            module_name.startswith(pattern) or f".{pattern.split('.')[-1]}" in module_name
            for pattern in self.forbidden_patterns
        )

    def visit_Import(self, node: ast.Import) -> None:
        """Check import statements."""
        for alias in node.names:
            if self._is_forbidden_import(alias.name):
                self.violations.append((node.lineno, f"Forbidden import: import {alias.name}"))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check from...import statements."""
        if node.module and self._is_forbidden_import(node.module):
            names = ", ".join(alias.name for alias in node.names)
            self.violations.append(
                (node.lineno, f"Forbidden import: from {node.module} import {names}")
            )
        self.generic_visit(node)


def check_core_imports(root_path: Path) -> List[Tuple[str, int, str]]:
    """
    Check all Python files in nav_insights/core for forbidden imports.

    Returns:
        List of violations as (file_path, line_number, message) tuples
    """
    violations = []
    core_path = root_path / "nav_insights" / "core"

    if not core_path.exists():
        print(f"Warning: Core path {core_path} does not exist")
        return violations

    # Get all Python files in core
    python_files = list(core_path.rglob("*.py"))

    for py_file in python_files:
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source, filename=str(py_file))
            checker = ImportViolationChecker(str(py_file))
            checker.visit(tree)

            for line_no, message in checker.violations:
                violations.append((str(py_file), line_no, message))

        except SyntaxError as e:
            violations.append((str(py_file), e.lineno or 0, f"Syntax error: {e}"))
        except Exception as e:
            violations.append((str(py_file), 0, f"Error processing file: {e}"))

    return violations


def main() -> int:
    """Main entry point."""
    root_path = Path(__file__).parent.parent
    violations = check_core_imports(root_path)

    if not violations:
        print("✅ All core imports are valid - no cross-layer violations found")
        return 0

    print("❌ Cross-layer import violations found:")
    print()

    for file_path, line_no, message in violations:
        rel_path = Path(file_path).relative_to(root_path)
        print(f"  {rel_path}:{line_no} - {message}")

    print()
    print(f"Total violations: {len(violations)}")
    print()
    print("Core modules must not import from domains/* or integrations/* packages.")
    print("This maintains the engine's reusability across different domain implementations.")

    return 1


if __name__ == "__main__":
    sys.exit(main())
