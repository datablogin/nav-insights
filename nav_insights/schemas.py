"""
Schemas for PaidSearchNav reasoning layer.
- Findings IR (AuditFindings)
- Actions (Action, ActionImpact)
- Insights (Insight, Section)

Notes:
- Keep analyzers as "facts engine"; these models only *structure* facts & outputs.
- All JSON exchanged with the tiny LLM should conform to these schemas.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional
from datetime import date, datetime


class AccountMeta(BaseModel):
    account_id: str = Field(..., description="Provider-native account ID")
    account_name: Optional[str] = Field(None, description="Human-readable account name")


class DateRange(BaseModel):
    start_date: date
    end_date: date


class Finding(BaseModel):
    """
    A single atomic fact discovered by an analyzer.
    Example categories: 'structure','keywords','quality','pmax','geo','budget','tracking'
    """
    id: str
    category: Literal["structure","keywords","quality","pmax","geo","budget","tracking","other"]
    summary: str
    # Evidence is raw snippets / rows / ids that substantiate the finding.
    evidence: Dict[str, Any] = Field(default_factory=dict)
    # Metrics should be numeric facts used by rules, e.g., wasted_spend_top_broad, broad_pct, qs_p25
    metrics: Dict[str, float] = Field(default_factory=dict)
    severity: Literal["low","medium","high"] = "medium"
    confidence: float = Field(0.9, ge=0.0, le=1.0)


class AuditFindings(BaseModel):
    """
    Container object produced by your analyzers—single source of truth
    consumed by the reasoning layer (rules + tiny LLM).
    """
    version: str = "1.0"
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    account: AccountMeta
    date_range: DateRange
    totals: Dict[str, float] = Field(default_factory=dict)
    findings: List[Finding]


class ActionImpact(BaseModel):
    spend_savings_usd: Optional[float] = None
    revenue_lift_usd: Optional[float] = None
    risk: Literal["low","medium","high"] = "low"


class Action(BaseModel):
    """
    A concrete recommendation the operator (or automation) can apply.
    - `type` can be a finite set like: tighten_match_types, add_negatives, budget_rebalance, geo_exclude, cap_pmax, etc.
    - `target` is a human-friendly pointer to the entities affected (e.g. 'top_broad_by_cost')
    - `params` are implementation details
    """
    id: str
    type: Literal[
        "tighten_match_types",
        "add_negatives",
        "budget_rebalance",
        "geo_exclude",
        "cap_pmax",
        "creative_refresh",
        "tracking_fix",
        "other"
    ] = "other"
    target: str
    params: Dict[str, Any] = Field(default_factory=dict)
    justification: str
    expected_impact: Optional[ActionImpact] = None
    priority: int = Field(3, ge=1, le=5)
    confidence: float = Field(0.85, ge=0.0, le=1.0)
    source_rule_id: Optional[str] = Field(None, description="Rule that produced this action (if any)")


class Section(BaseModel):
    title: str
    bullets: List[str] = Field(default_factory=list)
    metrics_highlights: Dict[str, Any] = Field(default_factory=dict)


class Insight(BaseModel):
    """
    Human-facing narrative + structured actions.
    This is the *only* shape the tiny LLM is allowed to return.
    """
    executive_summary: str
    sections: List[Section]
    actions: List[Action]
    metadata: Dict[str, Any] = Field(default_factory=dict)


def model_json_schema_safe(model_cls: type[BaseModel]) -> Dict[str, Any]:
    """
    Returns a JSON-schema for the provided Pydantic model.
    Works on Pydantic v2 (model_json_schema) and v1 (schema).
    """
    # Pydantic v2
    if hasattr(model_cls, "model_json_schema"):
        return model_cls.model_json_schema()
    # Pydantic v1
    return model_cls.schema()  # type: ignore


if __name__ == "__main__":
    # Print schema for Insight to stdout for quick inspection
    print(json.dumps(model_json_schema_safe(Insight), indent=2, default=str))
