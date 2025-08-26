#!/usr/bin/env python3
"""
Smoke tests for domain packs to verify basic functionality.

Tests that toy domain pack + search domain pack can be imported and used
without breaking the core engine architecture.
"""

import sys
import traceback
from pathlib import Path


def test_core_imports() -> bool:
    """Test that core modules can be imported successfully."""
    try:
        # Import and use core modules to test they work
        from nav_insights.core import findings_ir, rules, actions, dsl  # noqa: F401
        from nav_insights.core.insight import Insight  # noqa: F401
        from nav_insights.core.writer import LlamaCppClient  # noqa: F401

        print("✅ Core modules imported successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import core modules: {e}")
        traceback.print_exc()
        return False


def test_search_domain_pack() -> bool:
    """Test search domain pack functionality."""
    try:
        # Test search domain IR can be imported
        from nav_insights.domains.paid_search.ir import AuditFindingsSearch

        # Test basic instantiation
        test_ir = {
            "schema_version": "1.0.0",
            "account": {"account_id": "test_account"},
            "date_range": {"start_date": "2024-01-01", "end_date": "2024-01-31"},
            "totals": {},
            "findings": [],
        }

        # This should work without throwing
        AuditFindingsSearch.model_validate(test_ir)

        # Test rules can be loaded
        rules_path = (
            Path(__file__).parent.parent
            / "nav_insights"
            / "domains"
            / "paid_search"
            / "rules"
            / "default.yaml"
        )
        if rules_path.exists():
            from nav_insights.core.rules import _load_rules_cached

            _load_rules_cached(str(rules_path))

        print("✅ Search domain pack smoke test passed")
        return True

    except Exception as e:
        print(f"❌ Search domain pack smoke test failed: {e}")
        traceback.print_exc()
        return False


def test_toy_domain_pack() -> bool:
    """Test toy domain pack (minimal domain for testing)."""
    try:
        # For now, test that we can create a minimal domain structure
        # In the future, this could test a dedicated toy domain

        # Test that base IR can be used directly
        from nav_insights.core.findings_ir import AuditFindings

        test_ir = {
            "schema_version": "1.0.0",
            "account": {"account_id": "test_account"},
            "date_range": {"start_date": "2024-01-01", "end_date": "2024-01-31"},
            "totals": {},
            "findings": [],
        }

        AuditFindings.model_validate(test_ir)

        print("✅ Toy domain pack smoke test passed (using base IR)")
        return True

    except Exception as e:
        print(f"❌ Toy domain pack smoke test failed: {e}")
        traceback.print_exc()
        return False


def test_rules_engine_integration() -> bool:
    """Test that rules engine works with domain data."""
    try:
        from nav_insights.core.rules import evaluate_rules

        # Test with search domain rules if available
        rules_path = (
            Path(__file__).parent.parent
            / "nav_insights"
            / "domains"
            / "paid_search"
            / "rules"
            / "default.yaml"
        )

        if not rules_path.exists():
            print("⚠️  No search rules found, skipping rules engine integration test")
            return True

        # Use minimal test IR
        test_ir = {
            "schema_version": "1.0.0",
            "campaign_id": "smoke_test",
            "findings": [],
            "evidence": [],
            "totals": {},
            "aggregates": {
                "match_type": {
                    "broad_pct": 0.3  # Below threshold to avoid triggering rules
                }
            },
        }

        # This should not crash
        actions = evaluate_rules(test_ir, str(rules_path))
        print(f"✅ Rules engine integration test passed ({len(actions)} actions generated)")
        return True

    except Exception as e:
        print(f"❌ Rules engine integration test failed: {e}")
        traceback.print_exc()
        return False


def run_all_smoke_tests() -> int:
    """Run all smoke tests and return exit code."""
    print("🧪 Running domain pack smoke tests...\n")

    tests = [
        ("Core imports", test_core_imports),
        ("Search domain pack", test_search_domain_pack),
        ("Toy domain pack", test_toy_domain_pack),
        ("Rules engine integration", test_rules_engine_integration),
    ]

    results = {}

    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        results[test_name] = test_func()

    print(f"\n{'=' * 50}")
    print("SMOKE TEST RESULTS")
    print("=" * 50)

    passed = 0
    failed = 0

    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"{test_name:<30} {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\nPassed: {passed}, Failed: {failed}")

    if failed == 0:
        print("\n🎉 All smoke tests passed!")
        return 0
    else:
        print(f"\n💥 {failed} smoke test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_smoke_tests())
