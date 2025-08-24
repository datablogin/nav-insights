"""Basic tests for DSL functionality without pytest dependency."""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from nav_insights.core.dsl import (
    eval_expr, 
    value, 
    DSLRegistry, 
    get_registry, 
    register_dsl_function, 
    register_dsl_accessor
)


def test_value_accessor():
    """Test the value() accessor function."""
    data = {"a": {"b": {"c": 42}}}
    assert value("a.b.c", data) == 42
    assert value("a.b.missing", data) is None
    assert value("a.b.missing", data, "default") == "default"
    print("✓ value() accessor tests passed")


def test_registry_basic():
    """Test basic registry functionality."""
    registry = DSLRegistry()
    functions = registry.list_functions()
    accessors = registry.list_accessors()
    
    assert "min" in functions
    assert "max" in functions
    assert "value" in accessors
    
    def double(x):
        return x * 2
    
    registry.register_function("double", double)
    assert registry.get_function("double") is double
    print("✓ Registry basic tests passed")


def test_basic_expressions():
    """Test basic DSL expressions."""
    data = {
        "metrics": {
            "spend": 1000.0,
            "clicks": 500,
            "ctr": 0.05
        },
        "flags": {
            "has_data": True,
            "is_active": False
        }
    }
    
    # Literals
    assert eval_expr("42", data) == 42
    assert eval_expr("3.14", data) == 3.14
    assert eval_expr("True", data) is True
    assert eval_expr("False", data) is False
    assert eval_expr("None", data) is None
    
    # Arithmetic
    assert eval_expr("10 + 5", data) == 15
    assert eval_expr("20 - 8", data) == 12
    assert eval_expr("6 * 7", data) == 42
    assert eval_expr("15 / 3", data) == 5
    assert eval_expr("17 % 5", data) == 2
    
    # Comparisons
    assert eval_expr("5 == 5", data) is True
    assert eval_expr("5 != 6", data) is True
    assert eval_expr("3 < 5", data) is True
    assert eval_expr("5 <= 5", data) is True
    assert eval_expr("5 > 3", data) is True
    assert eval_expr("5 >= 5", data) is True
    
    # Logical operations
    assert eval_expr("True and True", data) is True
    assert eval_expr("True and False", data) is False
    assert eval_expr("True or False", data) is True
    assert eval_expr("False or False", data) is False
    assert eval_expr("not False", data) is True
    assert eval_expr("not True", data) is False
    
    # Value accessor
    assert eval_expr("value('metrics.spend')", data) == 1000.0
    assert eval_expr("value('metrics.clicks')", data) == 500
    assert eval_expr("value('missing.path')", data) is None
    assert eval_expr("value('missing.path', 'default')", data) == "default"
    
    # Built-in functions
    assert eval_expr("min(10, 5, 20)", data) == 5
    assert eval_expr("max(10, 5, 20)", data) == 20
    
    # Complex expressions
    assert eval_expr("value('metrics.spend') + 500", data) == 1500
    assert eval_expr("value('flags.has_data') and value('metrics.spend') > 0", data) is True
    assert eval_expr("not value('flags.is_active')", data) is True
    
    print("✓ Basic DSL expression tests passed")


def test_security():
    """Test that security restrictions work."""
    data = {}
    
    try:
        eval_expr("__import__", data)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Name not allowed" in str(e)
    
    try:
        eval_expr("open('/etc/passwd')", data)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Function" in str(e) and "not allowed" in str(e)
    
    print("✓ Security tests passed")


def test_registered_helpers():
    """Test that helper functions can be registered and used."""
    # Register helper functions directly
    def pct(x):
        """Format a decimal value as a percentage string."""
        try:
            return f"{float(x) * 100:.0f}%"
        except (TypeError, ValueError):
            return "n/a"
    
    def usd(x):
        """Format a numeric value as USD currency string."""
        try:
            return f"${float(x):,.0f}"
        except (TypeError, ValueError):
            return "n/a"
    
    register_dsl_function("pct", pct)
    register_dsl_function("usd", usd)
    
    data = {"conversion_rate": 0.025, "revenue": 5000}
    
    # Test pct helper
    result = eval_expr("pct(0.52)", data)
    assert result == "52%"
    
    # Test usd helper  
    result = eval_expr("usd(1300)", data)
    assert result == "$1,300"
    
    # Test in complex expression
    expr = "pct(value('conversion_rate'))"
    result = eval_expr(expr, data)
    print(f"Debug: pct result = {result!r}, type = {type(result)}")
    assert result == "2%"  # 0.025 * 100 = 2.5, rounded to 2%
    
    # Test error handling
    assert eval_expr("pct('invalid')", data) == "n/a"
    assert eval_expr("usd(None)", data) == "n/a"
    
    print("✓ Registered helper tests passed")


def test_graceful_none_handling():
    """Test graceful None behavior."""
    data = {
        "empty": None,
        "nested": {
            "empty": None
        }
    }
    
    # Should not raise exceptions
    assert eval_expr("value('empty.something')", data) is None
    assert eval_expr("value('nested.empty.deep')", data) is None
    assert eval_expr("value('empty.something', 'fallback')", data) == 'fallback'
    
    print("✓ Graceful None handling tests passed")


def run_all_tests():
    """Run all test functions."""
    print("Running DSL tests...")
    print()
    
    try:
        test_value_accessor()
        test_registry_basic()
        test_basic_expressions()
        test_security()
        test_registered_helpers()
        test_graceful_none_handling()
        
        print()
        print("🎉 All DSL tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)