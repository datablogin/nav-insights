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

