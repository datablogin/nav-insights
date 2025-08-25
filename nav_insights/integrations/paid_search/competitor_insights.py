from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from pydantic import BaseModel

from ...core.ir_base import (
    AuditFindings,
    AccountMeta,
    DateRange,
    Evidence,
    AnalyzerProvenance,
    Finding,
    Severity,
)


class CompetitorInsightsInput(BaseModel):
    analyzer: str
    customer_id: str
    analysis_period: Dict[str, str]
    timestamp: str
    summary: Dict[str, Any]
    detailed_findings: Dict[str, Any]


def parse_competitor_insights(data: Dict[str, Any]) -> AuditFindings:
    """Minimal parser scaffold mapping PaidSearchNav CompetitorInsightsAnalyzer output to AuditFindings.

    See docs/mappings/paid_search/competitor_insights_to_ir.md for full mapping details.
    """
    inp = CompetitorInsightsInput.model_validate(data)

    start = datetime.fromisoformat(inp.analysis_period["start_date"]).date()
    end = datetime.fromisoformat(inp.analysis_period["end_date"]).date()

    account = AccountMeta(account_id=inp.customer_id)
    date_range = DateRange(start_date=start, end_date=end)

    findings: List[Finding] = []

    # Primary competitors → one finding per item (minimal fields)
    for item in inp.detailed_findings.get("primary_competitors", []) or []:
        competitor = str(item.get("competitor", "unknown"))
        summary = f"Competitor overlap: {competitor}"
        severity = _map_priority(inp.summary.get("priority_level"))
        findings.append(
            Finding(
                id=f"COMPETITOR_{competitor}",
                category="other",  # consider 'competition' category in core
                summary=summary,
                severity=severity,
                metrics={
                    "impression_share_overlap": Decimal(
                        str(item.get("impression_share_overlap", 0))
                    ),
                    "shared_keywords": Decimal(str(item.get("shared_keywords", 0))),
                },
                dims={
                    "cost_competition_level": item.get("cost_competition_level"),
                    "competitive_threat_level": item.get("competitive_threat_level"),
                },
            )
        )

    evidence = Evidence(source="paid_search_nav.competitor_insights")
    prov = AnalyzerProvenance(
        name=inp.analyzer,
        version="unknown",
        finished_at=datetime.fromisoformat(inp.timestamp),
    )

    af = AuditFindings(
        account=account,
        date_range=date_range,
        totals={},  # minimal; leave defaults
        findings=findings,
        data_sources=[evidence],
        analyzers=[prov],
    )
    return af


def _map_priority(level: Any) -> Severity:
    s = str(level or "").lower()
    if s in ("critical", "high"):  # map CRITICAL→high
        return Severity.high
    if s == "medium":
        return Severity.medium
    return Severity.low
