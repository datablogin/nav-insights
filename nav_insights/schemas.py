from __future__ import annotations
import json
from typing import Any, Dict

# Canonical models are defined in core; import and re-export them here for convenience
from nav_insights.core.findings_ir import AuditFindings  # noqa: F401
from nav_insights.core.actions import Action, ActionImpact  # noqa: F401
from nav_insights.core.insight import Insight, Section  # noqa: F401


def model_json_schema_safe(model_cls) -> Dict[str, Any]:
    if hasattr(model_cls, "model_json_schema"):
        return model_cls.model_json_schema()
    return model_cls.schema()  # pydantic v1 fallback


if __name__ == "__main__":
    print(json.dumps(model_json_schema_safe(Insight), indent=2, default=str))
