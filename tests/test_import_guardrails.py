"""Tests for the import guardrails static checker."""

import tempfile
import ast
from pathlib import Path
from scripts.check_imports import ImportViolationChecker, check_core_imports


class TestImportViolationChecker:
    """Test the AST-based import violation checker."""

    def test_forbidden_import_patterns(self):
        """Test that forbidden patterns are correctly identified."""
        checker = ImportViolationChecker("test_file.py")

        # Test direct nav_insights.domains imports
        assert checker._is_forbidden_import("nav_insights.domains.paid_search")
        assert checker._is_forbidden_import("nav_insights.integrations.paid_search")

        # Test relative imports
        assert checker._is_forbidden_import(".domains")
        assert checker._is_forbidden_import(".integrations")

        # Test allowed imports
        assert not checker._is_forbidden_import("nav_insights.core.actions")
        assert not checker._is_forbidden_import("pydantic")
        assert not checker._is_forbidden_import("yaml")

    def test_ast_import_detection(self):
        """Test AST-based detection of import violations."""
        # Test regular import statement
        source_bad = "import nav_insights.domains.paid_search"
        tree = ast.parse(source_bad)
        checker = ImportViolationChecker("test.py")
        checker.visit(tree)

        assert len(checker.violations) == 1
        assert (
            "Forbidden import: import nav_insights.domains.paid_search" in checker.violations[0][1]
        )

    def test_ast_from_import_detection(self):
        """Test AST-based detection of from...import violations."""
        # Test from...import statement
        source_bad = "from nav_insights.integrations.paid_search import SomeClass"
        tree = ast.parse(source_bad)
        checker = ImportViolationChecker("test.py")
        checker.visit(tree)

        assert len(checker.violations) == 1
        assert (
            "Forbidden import: from nav_insights.integrations.paid_search import SomeClass"
            in checker.violations[0][1]
        )

    def test_allowed_imports(self):
        """Test that allowed imports don't trigger violations."""
        source_good = """
from nav_insights.core.actions import Action
import yaml
from pydantic import BaseModel
"""
        tree = ast.parse(source_good)
        checker = ImportViolationChecker("test.py")
        checker.visit(tree)

        assert len(checker.violations) == 0


class TestCoreImportChecker:
    """Integration tests for the full core import checker."""

    def test_current_core_modules_pass(self):
        """Test that current core modules don't have violations."""
        # This should pass with current codebase
        violations = check_core_imports(Path(__file__).parent.parent)
        assert len(violations) == 0, f"Found violations: {violations}"

    def test_simulated_violation_detection(self):
        """Test violation detection with temporary files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a simulated project structure
            tmp_path = Path(tmp_dir)
            core_path = tmp_path / "nav_insights" / "core"
            core_path.mkdir(parents=True)

            # Create a file with a bad import
            bad_file = core_path / "bad_module.py"
            bad_file.write_text("from nav_insights.domains.paid_search import SomeClass\n")

            # Check for violations
            violations = check_core_imports(tmp_path)

            assert len(violations) == 1
            assert "bad_module.py" in violations[0][0]
            assert "Forbidden import" in violations[0][2]
