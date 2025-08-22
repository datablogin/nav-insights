
import json, pathlib
from nav_insights.core.ir_base import AuditFindings
def test_ir_loads():
    p = pathlib.Path(__file__).parent.parent / "examples" / "sample_ir_search.json"
    data = json.loads(p.read_text())
    ir = AuditFindings.model_validate(data)
    assert ir.account.account_id == "123-456-7890"
    assert ir.totals.clicks >= 0
