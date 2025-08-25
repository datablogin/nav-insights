"""Comprehensive tests for the DSL expression evaluator and registry system."""

import pytest
from nav_insights.core.dsl import (
    eval_expr,
    value,
    DSLRegistry,
    get_registry,
    register_dsl_function,
    ExpressionError,
    ParseError,
    UnsupportedNodeError,
    HelperNotFoundError,
    ResourceLimitError,
)


class TestValueAccessor:
    """Test the value() accessor function for safe path traversal."""

    def test_simple_dict_access(self):
        data = {"a": {"b": {"c": 42}}}
        assert value("a.b.c", data) == 42

    def test_missing_key_returns_default(self):
        data = {"a": {"b": {}}}
        assert value("a.b.missing", data) is None
        assert value("a.b.missing", data, "default") == "default"

    def test_none_in_path_returns_default(self):
        data = {"a": {"b": None}}
        assert value("a.b.c", data) is None
        assert value("a.b.c", data, "fallback") == "fallback"

    def test_object_attribute_access(self):
        class TestObj:
            def __init__(self):
                self.nested = TestObj() if hasattr(self, "nested") else None
                self.value = 100

        obj = TestObj()
        obj.nested = TestObj()
        obj.nested.value = 200

        # Object attribute access is now blocked for security - should return None
        assert value("nested.value", obj) is None
        assert value("missing.attr", obj) is None

    def test_mixed_dict_object_access(self):
        class TestObj:
            def __init__(self):
                self.data = {"key": "value"}

        obj = TestObj()
        # Object attribute access is now blocked for security - should return None
        assert value("data.key", obj) is None


class TestDSLRegistry:
    """Test the DSL registry system."""

    def test_registry_initialization(self):
        registry = DSLRegistry()
        functions = registry.list_functions()
        accessors = registry.list_accessors()

        assert "min" in functions
        assert "max" in functions
        assert "value" in accessors

    def test_register_function(self):
        registry = DSLRegistry()

        def double(x):
            return x * 2

        registry.register_function("double", double)
        assert registry.get_function("double") is double
        assert "double" in registry.list_functions()

    def test_register_duplicate_function_raises(self):
        registry = DSLRegistry()

        def func1():
            return 1

        def func2():
            return 2

        registry.register_function("test", func1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register_function("test", func2)

    def test_register_non_callable_raises(self):
        registry = DSLRegistry()

        with pytest.raises(ValueError, match="must be callable"):
            registry.register_function("test", "not_callable")

    def test_register_accessor(self):
        registry = DSLRegistry()

        def make_accessor(root):
            def accessor(key):
                return root.get(key, "not found")

            return accessor

        registry.register_accessor("get", make_accessor)
        assert registry.get_accessor("get") is make_accessor

    def test_clear_registry(self):
        registry = DSLRegistry()
        registry.register_function("test", lambda: None)
        registry.clear()

        assert registry.get_function("test") is None
        assert "min" in registry.list_functions()  # Built-ins preserved

    def test_global_registry_functions(self):
        # Clean up first
        get_registry().clear()

        def test_func():
            return "test_result"

        register_dsl_function("global_test", test_func)
        assert get_registry().get_function("global_test") is test_func

        # Cleanup
        get_registry().clear()


class TestDSLExpressions:
    """Test DSL expression evaluation with 30+ test cases as required."""

    @pytest.fixture
    def sample_data(self):
        return {
            "metrics": {
                "spend": 1000.0,
                "clicks": 500,
                "impressions": 10000,
                "ctr": 0.05,
                "cpc": 2.0,
            },
            "aggregates": {"match_type": {"broad_pct": 0.6, "exact_pct": 0.3, "phrase_pct": 0.1}},
            "flags": {"has_data": True, "is_active": False},
            "nested": {"deep": {"value": 42}},
            "empty": None,
            "zero": 0,
        }

    # Literals (Tests 1-5)
    def test_integer_literal(self, sample_data):
        assert eval_expr("42", sample_data) == 42

    def test_float_literal(self, sample_data):
        assert eval_expr("3.14", sample_data) == 3.14

    def test_string_literal(self, sample_data):
        assert eval_expr("'hello'", sample_data) == "hello"

    def test_boolean_literals(self, sample_data):
        assert eval_expr("True", sample_data) is True
        assert eval_expr("False", sample_data) is False

    def test_none_literal(self, sample_data):
        assert eval_expr("None", sample_data) is None

    # Arithmetic operations (Tests 6-10)
    def test_addition(self, sample_data):
        assert eval_expr("10 + 5", sample_data) == 15
        assert eval_expr("value('metrics.spend') + 500", sample_data) == 1500

    def test_subtraction(self, sample_data):
        assert eval_expr("20 - 8", sample_data) == 12
        assert eval_expr("value('metrics.impressions') - 1000", sample_data) == 9000

    def test_multiplication(self, sample_data):
        assert eval_expr("6 * 7", sample_data) == 42
        assert eval_expr("value('metrics.clicks') * 2", sample_data) == 1000

    def test_division(self, sample_data):
        assert eval_expr("15 / 3", sample_data) == 5
        assert eval_expr("value('metrics.spend') / 10", sample_data) == 100

    def test_modulo(self, sample_data):
        assert eval_expr("17 % 5", sample_data) == 2
        assert eval_expr("value('metrics.clicks') % 100", sample_data) == 0

    # Comparison operations (Tests 11-16)
    def test_equality(self, sample_data):
        assert eval_expr("5 == 5", sample_data) is True
        assert eval_expr("5 == 6", sample_data) is False
        assert eval_expr("value('metrics.clicks') == 500", sample_data) is True

    def test_inequality(self, sample_data):
        assert eval_expr("5 != 6", sample_data) is True
        assert eval_expr("5 != 5", sample_data) is False

    def test_less_than(self, sample_data):
        assert eval_expr("3 < 5", sample_data) is True
        assert eval_expr("5 < 3", sample_data) is False
        assert eval_expr("value('metrics.ctr') < 0.1", sample_data) is True

    def test_less_equal(self, sample_data):
        assert eval_expr("5 <= 5", sample_data) is True
        assert eval_expr("5 <= 6", sample_data) is True
        assert eval_expr("6 <= 5", sample_data) is False

    def test_greater_than(self, sample_data):
        assert eval_expr("5 > 3", sample_data) is True
        assert eval_expr("3 > 5", sample_data) is False
        assert eval_expr("value('aggregates.match_type.broad_pct') > 0.5", sample_data) is True

    def test_greater_equal(self, sample_data):
        assert eval_expr("5 >= 5", sample_data) is True
        assert eval_expr("6 >= 5", sample_data) is True
        assert eval_expr("5 >= 6", sample_data) is False

    # Logical operations (Tests 17-20)
    def test_and_operator(self, sample_data):
        assert eval_expr("True and True", sample_data) is True
        assert eval_expr("True and False", sample_data) is False
        assert (
            eval_expr("value('flags.has_data') and value('metrics.spend') > 0", sample_data) is True
        )

    def test_or_operator(self, sample_data):
        assert eval_expr("True or False", sample_data) is True
        assert eval_expr("False or False", sample_data) is False
        assert (
            eval_expr("value('flags.is_active') or value('metrics.clicks') > 0", sample_data)
            is True
        )

    def test_not_operator(self, sample_data):
        assert eval_expr("not False", sample_data) is True
        assert eval_expr("not True", sample_data) is False
        assert eval_expr("not value('flags.is_active')", sample_data) is True

    def test_complex_logical(self, sample_data):
        expr = "value('flags.has_data') and (value('metrics.ctr') > 0.01 or value('metrics.spend') > 500)"
        assert eval_expr(expr, sample_data) is True

    # Value accessor tests (Tests 21-25)
    def test_value_simple_path(self, sample_data):
        assert eval_expr("value('metrics.spend')", sample_data) == 1000.0

    def test_value_deep_path(self, sample_data):
        assert eval_expr("value('nested.deep.value')", sample_data) == 42

    def test_value_with_default(self, sample_data):
        assert eval_expr("value('missing.path', 'default')", sample_data) == "default"

    def test_value_missing_returns_none(self, sample_data):
        assert eval_expr("value('missing.path')", sample_data) is None

    def test_value_none_path_graceful(self, sample_data):
        assert eval_expr("value('empty.something')", sample_data) is None

    # Built-in functions (Tests 26-27)
    def test_min_function(self, sample_data):
        assert eval_expr("min(10, 5, 20)", sample_data) == 5
        assert eval_expr("min(value('metrics.ctr'), 0.1)", sample_data) == 0.05

    def test_max_function(self, sample_data):
        assert eval_expr("max(10, 5, 20)", sample_data) == 20
        assert eval_expr("max(value('metrics.clicks'), 1000)", sample_data) == 1000

    # Unary operations (Tests 28-29)
    def test_unary_minus(self, sample_data):
        assert eval_expr("-5", sample_data) == -5
        assert eval_expr("-value('metrics.spend')", sample_data) == -1000.0

    def test_unary_not_with_comparison(self, sample_data):
        assert eval_expr("not (5 > 10)", sample_data) is True

    # Complex expressions (Tests 30-35)
    def test_complex_arithmetic(self, sample_data):
        expr = "(value('metrics.spend') + 500) * 2 - 100"
        assert eval_expr(expr, sample_data) == 2900  # (1000 + 500) * 2 - 100

    def test_complex_comparison_chain(self, sample_data):
        expr = "value('metrics.ctr') > 0.01 and value('metrics.ctr') < 0.1"
        assert eval_expr(expr, sample_data) is True

    def test_mixed_operations(self, sample_data):
        expr = "value('metrics.clicks') / value('metrics.impressions') == value('metrics.ctr')"
        assert eval_expr(expr, sample_data) is True

    def test_nested_function_calls(self, sample_data):
        expr = "max(min(value('metrics.ctr'), 0.1), 0.01)"
        assert eval_expr(expr, sample_data) == 0.05

    def test_boolean_arithmetic_mix(self, sample_data):
        expr = "(value('flags.has_data') and value('metrics.spend') > 0) or (not value('flags.is_active'))"
        assert eval_expr(expr, sample_data) is True

    def test_percentage_calculation(self, sample_data):
        expr = "value('aggregates.match_type.broad_pct') >= 0.5 and value('aggregates.match_type.exact_pct') < 0.4"
        assert eval_expr(expr, sample_data) is True


class TestDSLSecurity:
    """Test that the DSL properly blocks dangerous operations."""

    def test_blocks_arbitrary_names(self):
        with pytest.raises(UnsupportedNodeError, match="Name not allowed"):
            eval_expr("__import__", {})

    def test_blocks_attribute_access(self):
        with pytest.raises(UnsupportedNodeError, match="Node not allowed"):
            eval_expr("value.__class__", {})

    def test_blocks_arbitrary_functions(self):
        with pytest.raises(HelperNotFoundError, match="not found"):
            eval_expr("open('/etc/passwd')", {})

    def test_blocks_exec_eval(self):
        with pytest.raises(HelperNotFoundError, match="not found"):
            eval_expr("eval('1+1')", {})

    def test_blocks_import_statements(self):
        # This would be caught at parse time
        with pytest.raises(ParseError):
            eval_expr("import os", {})

    def test_allows_safe_builtin_constants(self):
        # These should work fine
        assert eval_expr("True", {}) is True
        assert eval_expr("False", {}) is False
        assert eval_expr("None", {}) is None


class TestRegisteredHelpers:
    """Test that registered helper functions work in expressions."""

    def setup_method(self):
        # Ensure helpers are registered for each test
        from nav_insights.core.dsl import get_registry

        registry = get_registry()

        # Check if helpers are already registered, if not register them
        if not registry.get_function("pct"):

            def pct(x):
                """Format a decimal value as a percentage string."""
                try:
                    return f"{float(x) * 100:.0f}%"
                except (TypeError, ValueError):
                    return "n/a"

            registry.register_function("pct", pct)

        if not registry.get_function("usd"):

            def usd(x):
                """Format a numeric value as USD currency string."""
                try:
                    return f"${float(x):,.0f}"
                except (TypeError, ValueError):
                    return "n/a"

            registry.register_function("usd", usd)

    def test_pct_helper_function(self):
        result = eval_expr("pct(0.52)", {})
        assert result == "52%"

    def test_usd_helper_function(self):
        result = eval_expr("usd(1300)", {})
        assert result == "$1,300"

    def test_helpers_in_complex_expression(self):
        data = {"conversion_rate": 0.025, "revenue": 5000}
        expr = (
            "pct(value('conversion_rate')) + ' conversion rate generates ' + usd(value('revenue'))"
        )
        result = eval_expr(expr, data)
        assert result == "2% conversion rate generates $5,000"

    def test_helpers_handle_invalid_input(self):
        assert eval_expr("pct('invalid')", {}) == "n/a"
        assert eval_expr("usd(None)", {}) == "n/a"


class TestCustomRegistryUsage:
    """Test using custom registry with domain-specific functions."""

    def test_custom_registry_with_domain_function(self):
        registry = DSLRegistry()

        def quality_score_category(score):
            if score >= 7:
                return "high"
            elif score >= 4:
                return "medium"
            else:
                return "low"

        registry.register_function("qs_category", quality_score_category)

        data = {"keyword": {"quality_score": 8}}
        result = eval_expr("qs_category(value('keyword.quality_score'))", data, registry)
        assert result == "high"

    def test_custom_accessor(self):
        registry = DSLRegistry()

        def make_safe_divide(root):
            def safe_divide(a, b):
                try:
                    return float(a) / float(b) if b != 0 else 0
                except (TypeError, ValueError):
                    return 0

            return safe_divide

        registry.register_accessor("safe_div", make_safe_divide)

        data = {"a": 10, "b": 0}
        result = eval_expr("safe_div(value('a'), value('b'))", data, registry)
        assert result == 0


class TestNoneHandling:
    """Test graceful None handling in arithmetic and comparisons."""

    def test_none_arithmetic_operations(self):
        """Test that arithmetic with None returns None."""
        data = {"null_val": None, "num": 5}

        # Addition with None
        assert eval_expr("value('null_val') + 1", data) is None
        assert eval_expr("1 + value('null_val')", data) is None
        assert eval_expr("value('null_val') + value('num')", data) is None

        # Subtraction with None
        assert eval_expr("value('null_val') - 1", data) is None
        assert eval_expr("10 - value('null_val')", data) is None

        # Multiplication with None
        assert eval_expr("value('null_val') * 5", data) is None
        assert eval_expr("5 * value('null_val')", data) is None

        # Division with None
        assert eval_expr("value('null_val') / 2", data) is None
        assert eval_expr("10 / value('null_val')", data) is None

        # Modulo with None
        assert eval_expr("value('null_val') % 3", data) is None
        assert eval_expr("7 % value('null_val')", data) is None

    def test_none_comparisons(self):
        """Test None comparison semantics."""
        data = {"null_val": None, "num": 5}

        # None == None is True
        assert eval_expr("value('null_val') == None", data) is True
        assert eval_expr("None == value('null_val')", data) is True

        # None != None is False
        assert eval_expr("value('null_val') != None", data) is False

        # None vs non-None comparisons
        assert eval_expr("value('null_val') == 5", data) is False
        assert eval_expr("5 == value('null_val')", data) is False
        assert eval_expr("value('null_val') != 5", data) is True
        assert eval_expr("5 != value('null_val')", data) is True

        # Other comparisons with None return False
        assert eval_expr("value('null_val') < 5", data) is False
        assert eval_expr("value('null_val') <= 5", data) is False
        assert eval_expr("value('null_val') > 5", data) is False
        assert eval_expr("value('null_val') >= 5", data) is False
        assert eval_expr("5 < value('null_val')", data) is False
        assert eval_expr("5 > value('null_val')", data) is False


class TestErrorTaxonomy:
    """Test the new error type hierarchy."""

    def test_parse_error(self):
        """Test ParseError for syntax errors."""
        with pytest.raises(ParseError):
            eval_expr("1 +", {})  # Incomplete expression

        with pytest.raises(ParseError):
            eval_expr("(1 + 2", {})  # Missing closing paren

    def test_unsupported_node_error(self):
        """Test UnsupportedNodeError for disallowed operations."""
        with pytest.raises(UnsupportedNodeError, match="Name not allowed"):
            eval_expr("__import__", {})

        with pytest.raises(UnsupportedNodeError, match="Node not allowed"):
            eval_expr("lambda x: x", {})  # Lambda not allowed

    def test_helper_not_found_error(self):
        """Test HelperNotFoundError for missing functions."""
        with pytest.raises(HelperNotFoundError, match="Function 'nonexistent' not found"):
            eval_expr("nonexistent(1, 2)", {})

    def test_resource_limit_error(self):
        """Test ResourceLimitError for exceeding limits."""
        # Test expression length limit
        long_expr = "1 + " * 500 + "1"  # Very long expression
        with pytest.raises(ResourceLimitError, match="Expression length .* exceeds limit"):
            eval_expr(long_expr, {}, max_length=100)

        # Test AST depth limit
        deep_expr = "1" + " + 1" * 15  # Deep binary operations
        with pytest.raises(ResourceLimitError, match="AST depth exceeds limit"):
            eval_expr(deep_expr, {}, max_depth=10)

    def test_expression_error(self):
        """Test ExpressionError for evaluation errors."""
        with pytest.raises(ExpressionError, match="Arithmetic error"):
            eval_expr("1 / 0", {})  # Division by zero

        with pytest.raises(ExpressionError, match="Comparison error"):
            eval_expr("'string' < 5", {})  # Invalid comparison


class TestShortCircuiting:
    """Test proper short-circuit behavior in boolean operations."""

    def test_and_short_circuit(self):
        """Test that AND short-circuits properly."""
        data = {"true_val": True, "false_val": False}

        # Should short-circuit and not evaluate the second operand
        result = eval_expr(
            "value('false_val') and (1 / 0)", data
        )  # Would raise if not short-circuited
        assert result is False

        # Should evaluate all operands when all are truthy
        result = eval_expr("value('true_val') and 5 and 'hello'", data)
        assert result == "hello"  # Returns last truthy value

        # Should return first falsy value
        result = eval_expr("value('true_val') and 0 and value('false_val')", data)
        assert result == 0

    def test_or_short_circuit(self):
        """Test that OR short-circuits properly."""
        data = {"true_val": True, "false_val": False}

        # Should short-circuit and not evaluate the second operand
        result = eval_expr(
            "value('true_val') or (1 / 0)", data
        )  # Would raise if not short-circuited
        assert result is True

        # Should return first truthy value
        result = eval_expr("value('false_val') or 5 or 'hello'", data)
        assert result == 5

        # Should evaluate all operands when all are falsy
        result = eval_expr("value('false_val') or 0 or ''", data)
        assert result == ""  # Returns last falsy value


class TestResourceLimits:
    """Test resource limit enforcement."""

    def test_expression_length_limit(self):
        """Test expression length limiting."""
        short_expr = "1 + 2"
        assert eval_expr(short_expr, {}, max_length=10) == 3

        with pytest.raises(ResourceLimitError):
            eval_expr(short_expr, {}, max_length=3)  # Too short

    def test_ast_depth_limit(self):
        """Test AST depth limiting."""
        shallow_expr = "1 + 2 + 3"
        assert eval_expr(shallow_expr, {}, max_depth=5) == 6

        deep_expr = "1" + " + 1" * 15  # Deep binary operations
        with pytest.raises(ResourceLimitError):
            eval_expr(deep_expr, {}, max_depth=10)


class TestSecuredValueAccess:
    """Test the more secure value() function."""

    def test_dict_access_allowed(self):
        """Test that dict access still works."""
        data = {"a": {"b": {"c": 42}}}
        assert value("a.b.c", data) == 42

    def test_object_attribute_access_blocked(self):
        """Test that arbitrary object attribute access is blocked."""

        class TestObj:
            def __init__(self):
                self.dangerous = "blocked"

        obj = TestObj()
        # Should return default instead of accessing attributes
        assert value("dangerous", obj, "safe") == "safe"

    def test_pydantic_model_access(self):
        """Test that Pydantic models work via model_dump."""

        # This test would need pydantic installed
        # For now, just test the hasattr check logic
        class MockPydanticModel:
            def model_dump(self):
                return {"field": "value"}

        model = MockPydanticModel()
        assert value("field", model) == "value"

    def test_dict_like_access(self):
        """Test dict-like objects with get method."""

        class DictLike:
            def __init__(self, data):
                self._data = data

            def get(self, key, default=None):
                return self._data.get(key, default)

            def __getitem__(self, key):
                return self._data[key]

        obj = DictLike({"key": "value"})
        assert value("key", obj) == "value"
        assert value("missing", obj, "default") == "default"
