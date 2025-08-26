from __future__ import annotations

import pytest

from nav_insights.core.errors import CoreError, to_core_error
from nav_insights.core import dsl_exceptions as dslx


def test_core_error_serialization():
    err = CoreError(
        code="invalid_metric",
        category="parser.keyword",
        message="Cost must be non-negative",
        severity="error",
        context={"field": "cost", "value": "-1"},
    )
    d = err.to_dict()
    assert d["code"] == "invalid_metric"
    assert d["category"] == "parser.keyword"
    assert d["severity"] == "error"
    assert d["context"]["field"] == "cost"


def test_to_core_error_maps_dsl_exceptions():
    e = dslx.ResourceLimitError("depth exceeded")
    ce = to_core_error(e)
    assert isinstance(ce, CoreError)
    assert ce.code == "resource_limit"
    assert ce.category == "dsl"
    assert "depth exceeded" in ce.message


def test_to_core_error_fallback():
    try:
        raise RuntimeError("boom")
    except RuntimeError as e:
        ce = to_core_error(e, default_category="service")
        assert ce.code == "unhandled_exception"
        assert ce.category == "service"
        assert "boom" in ce.message
