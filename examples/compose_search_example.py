
import json
import pathlib

from nav_insights.core.rules import evaluate_rules

BASE = pathlib.Path(__file__).parent
ir = json.loads((BASE / "sample_ir_search.json").read_text())
rules_path = str(BASE.parent / "nav_insights" / "domains" / "paid_search" / "rules" / "default.yaml")
actions = evaluate_rules(ir, rules_path)
for a in actions:
    print(a.model_dump())
