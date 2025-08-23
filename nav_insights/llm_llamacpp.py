from __future__ import annotations

# Keep this module as a thin wrapper to avoid duplicate client implementations.
from nav_insights.core.writer import LlamaCppClient  # re-export

__all__ = ["LlamaCppClient"]

if __name__ == "__main__":
    # Optional quick demo
    from nav_insights.core.insight import Insight
    client = LlamaCppClient(base_url="http://localhost:8000/v1", model="local")
    system = "You return ONLY minified JSON that validates the provided schema."
    user = "Return an Insight with a placeholder executive summary and no actions."
    insight = client.generate_structured(Insight, system, user)
    print(insight.model_dump_json(indent=2))
