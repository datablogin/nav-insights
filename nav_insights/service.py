from __future__ import annotations
import json
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from nav_insights.core.rules import evaluate_rules
from nav_insights.core.actions import Action
from nav_insights.core.insight import Insight
from nav_insights.core.writer import compose_insight_json

app = FastAPI(title="nav_insights")

DEFAULT_RULES = Path(__file__).parent / "domains" / "paid_search" / "rules" / "default.yaml"


class ActionsRequest(BaseModel):
    ir: dict
    rules_path: Optional[str] = None


@app.post("/v1/actions:evaluate")
def actions_evaluate(req: ActionsRequest):
    rules_path = req.rules_path or str(DEFAULT_RULES)
    actions = evaluate_rules(req.ir, rules_path)
    return [a.model_dump() for a in actions]


class InsightsRequest(BaseModel):
    ir: dict
    actions: Optional[List[dict]] = None
    base_url: str = "http://localhost:8000/v1"
    model: str = "local"


@app.post("/v1/insights:compose")
def insights_compose(req: InsightsRequest):
    actions = [Action(**a) for a in req.actions] if req.actions else evaluate_rules(req.ir, str(DEFAULT_RULES))
    insight = compose_insight_json(req.ir, actions, Insight, base_url=req.base_url, model=req.model)
    return json.loads(insight.model_dump_json())
