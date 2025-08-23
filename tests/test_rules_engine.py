import json, pathlib
from nav_insights.core.rules import evaluate_rules

def test_rules_emit_expected_actions():
    base = pathlib.Path(__file__).parent.parent
    ir = json.loads((base / "examples" / "sample_ir_search.json").read_text())
    rules_path = str(base / "nav_insights" / "domains" / "paid_search" / "rules" / "default.yaml")
    actions = evaluate_rules(ir, rules_path)
    assert len(actions) >= 3
    src_ids = {a.source_rule_id for a in actions}
    assert {"BROAD_TOO_HIGH_LOW_QS", "PMAX_QUERY_CANNIBALIZATION", "GEO_WASTE_OUTLIERS"} <= src_ids
