
from __future__ import annotations
from typing import Any, Dict, Optional, Literal
from pydantic import BaseModel, Field, confloat

class ActionImpact(BaseModel):
    spend_savings_usd: Optional[float] = None
    revenue_lift_usd: Optional[float] = None
    risk: Literal["low","medium","high"] = "low"

class Action(BaseModel):
    id: str
    type: Literal["tighten_match_types","add_negatives","budget_rebalance","geo_exclude","cap_pmax","creative_refresh","tracking_fix","other"] = "other"
    target: str
    params: Dict[str, Any] = Field(default_factory=dict)
    justification: str
    expected_impact: Optional[ActionImpact] = None
    priority: int = Field(3, ge=1, le=5)
    confidence: confloat(ge=0.0, le=1.0) = 0.85
    source_rule_id: Optional[str] = None
