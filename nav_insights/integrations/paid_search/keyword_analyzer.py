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


class KeywordAnalyzerInput(BaseModel):
    analyzer: str
    customer_id: str
    analysis_period: Dict[str, str]
    timestamp: str
    summary: Dict[str, Any]
    detailed_findings: Dict[str, Any]


def parse_keyword_analyzer(data: Dict[str, Any]) -> AuditFindings:
    """Minimal parser scaffold mapping PaidSearchNav KeywordAnalyzer output to AuditFindings.

    See docs/mappings/paid_search/keyword_analyzer_to_ir.md for full mapping details.
    """
    inp = KeywordAnalyzerInput.model_validate(data)

    start = datetime.fromisoformat(inp.analysis_period["start_date"]).date()
    end = datetime.fromisoformat(inp.analysis_period["end_date"]).date()

    account = AccountMeta(account_id=inp.customer_id)
    date_range = DateRange(start_date=start, end_date=end)

    findings: List[Finding] = []

    # Underperforming keywords → findings
    for item in inp.detailed_findings.get("underperforming_keywords", []) or []:
        name = str(item.get("name", "unknown"))
        match_type = str(item.get("match_type", ""))
        recommendation = item.get("recommendation")
        summary = f"Underperforming keyword '{name}' ({match_type})"
        severity = _map_priority(inp.summary.get("priority_level"))
        metrics: Dict[str, Decimal] = {"cost": Decimal(str(item.get("cost", 0))), "conversions": Decimal(str(item.get("conversions", 0)))}
        if (cpa := item.get("cpa")) not in (None, "N/A"):
            metrics["cpa"] = Decimal(str(cpa))
        findings.append(
            Finding(
                id=f"KW_UNDER_{name}",
                category="keywords",
                summary=summary,
                description=recommendation,
                severity=severity,
                dims={"match_type": match_type, "campaign": item.get("campaign")},
                metrics=metrics,
            )
        )

    # Top performers → findings
    for item in inp.detailed_findings.get("top_performers", []) or []:
        name = str(item.get("name", "unknown"))
        match_type = str(item.get("match_type", ""))
        recommendation = item.get("recommendation")
        summary = f"Top performer '{name}' ({match_type})"
        severity = _map_priority(inp.summary.get("priority_level"))
        metrics: Dict[str, Decimal] = {"cost": Decimal(str(item.get("cost", 0))), "conversions": Decimal(str(item.get("conversions", 0)))}
        if (cpa := item.get("cpa")) is not None:
            metrics["cpa"] = Decimal(str(cpa))
        findings.append(
            Finding(
                id=f"KW_TOP_{name}",
                category="keywords",
                summary=summary,
                description=recommendation,
                severity=severity,
                dims={"match_type": match_type, "campaign": item.get("campaign")},
                metrics=metrics,
            )
        )

    evidence = Evidence(source="paid_search_nav.keyword")
    prov = AnalyzerProvenance(name=inp.analyzer, finished_at=datetime.fromisoformat(inp.timestamp))

    af = AuditFindings(
        account=account,
        date_range=date_range,
        totals={},
        findings=findings,
        data_sources=[evidence],
        analyzers=[prov],
    )
    return af


def _map_priority(level: Any) -> Severity:
    s = str(level or "").lower()
    if s in ("critical", "high"):
        return Severity.high
    if s == "medium":
        return Severity.medium
    return Severity.low

