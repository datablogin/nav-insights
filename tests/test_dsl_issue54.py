"""Comprehensive tests for the DSL expression evaluator and registry system.

Extended with short-circuit and None-semantics tests (Issue #54).
"""

import pytest
from nav_insights.core.dsl import eval_expr


class TestShortCircuitAndNoneSemantics:
    def test_short_circuit_and(self):
        # Right side raises if evaluated; must short-circuit
        assert eval_expr("False and (1/0)", {}) is False

    def test_short_circuit_or(self):
        assert eval_expr("True or (1/0)", {}) is True

    def test_none_arithmetic_rules(self):
        # Arithmetic with None => None
        assert eval_expr("None + 1", {}) is None
        assert eval_expr("1 + None", {}) is None
        assert eval_expr("None * 5", {}) is None

    def test_none_comparison_rules(self):
        # Comparisons with None => False except equality to None
        assert eval_expr("None == None", {}) is True
        assert eval_expr("None != None", {}) is False
        assert eval_expr("None < 1", {}) is False
        assert eval_expr("None > 1", {}) is False
        assert eval_expr("1 == None", {}) is False
        assert eval_expr("1 != None", {}) is True

    def test_none_logical_rules(self):
        # Logical ops: None treated as False
        assert eval_expr("None and True", {}) is False
        assert eval_expr("None or True", {}) is True
        assert eval_expr("not None", {}) is True


class TestResourceLimitsAndErrors:
    def test_expression_length_limit(self):
        long_expr = "1+" * 2000  # length > 1024
        with pytest.raises(Exception) as exc:
            eval_expr(long_expr, {})
        assert "Expression length" in str(exc.value)

    def test_ast_depth_limit(self):
        # Build a deeply nested unary expression: not(not(...not True))
        depth = 40
        expr = "not (" * depth + "True" + ")" * depth
        with pytest.raises(Exception) as exc:
            eval_expr(expr, {}, max_depth=25)
        assert "AST depth" in str(exc.value)

    def test_helper_not_found(self):
        with pytest.raises(Exception) as exc:
            eval_expr("unknown_func(1)", {})
        assert "not found" in str(exc.value)

    def test_unsupported_node(self):
        # Attribute access should be rejected
        with pytest.raises(Exception) as exc:
            eval_expr("value.__class__", {})
        assert "Node not allowed" in str(exc.value)

    def test_builtin_funcs_ok(self):
        assert eval_expr("min(10, 5, 20)", {}) == 5
        assert eval_expr("max(10, 5, 20)", {}) == 20

