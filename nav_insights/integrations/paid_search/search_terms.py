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


class SearchTermsInput(BaseModel):
    analyzer: str
    customer_id: str | None = None
    analysis_period: Dict[str, str] | None = None
    timestamp: str | None = None
    summary: Dict[str, Any] | None = None
    detailed_findings: Dict[str, Any]


def parse_search_terms(data: Dict[str, Any]) -> AuditFindings:
    """Minimal parser scaffold mapping PaidSearchNav SearchTermsAnalyzer output to AuditFindings.

    See docs/mappings/paid_search/search_terms_to_ir.md for details.
    """
    inp = SearchTermsInput.model_validate(data)

    # Fallbacks if some headers missing (Topgolf sample shape differs)
    customer_id = inp.customer_id or str(
        data.get("customer_id") or data.get("account_id") or "unknown"
    )
    timestamp = inp.timestamp or str(data.get("timestamp") or datetime.utcnow().isoformat())

    if inp.analysis_period:
        start = datetime.fromisoformat(inp.analysis_period["start_date"]).date()
        end = datetime.fromisoformat(inp.analysis_period["end_date"]).date()
    else:
        # derive a dummy window if not present
        dt = datetime.fromisoformat(timestamp)
        start = dt.date()
        end = dt.date()

    account = AccountMeta(account_id=customer_id)
    date_range = DateRange(start_date=start, end_date=end)

    findings: List[Finding] = []

    # Wasteful search terms
    for item in inp.detailed_findings.get("wasteful_search_terms") or []:
        term = str(item.get("term", ""))
        kw = item.get("keyword_triggered")
        summary = f"Wasteful search term '{term}' — add negative"
        severity = _map_priority(inp.summary.get("priority_level") if inp.summary else None)
        findings.append(
            Finding(
                id=f"ST_WASTE_{term}",
                category="keywords",
                summary=summary,
                description=item.get("recommendation"),
                severity=severity,
                dims={"keyword_triggered": kw} if kw else {},
                metrics={
                    "cost": Decimal(str(item.get("cost", 0))),
                    "conversions": Decimal(str(item.get("conversions", 0))),
                    "clicks": Decimal(str(item.get("clicks", 0))),
                },
            )
        )

    # Negative keyword suggestions
    for item in inp.detailed_findings.get("negative_keyword_suggestions") or []:
        neg = str(item.get("negative_keyword", ""))
        summary = f"Negative keyword suggestion '{neg}'"
        severity = _map_priority(inp.summary.get("priority_level") if inp.summary else None)
        findings.append(
            Finding(
                id=f"ST_NEG_{neg}",
                category="keywords",
                summary=summary,
                description=item.get("reason"),
                severity=severity,
                dims={"match_type": item.get("match_type")},
                metrics={"estimated_savings_usd": Decimal(str(item.get("estimated_savings", 0)))},
            )
        )

    evidence = Evidence(source="paid_search_nav.search_terms")
    prov = AnalyzerProvenance(
        name=inp.analyzer or "SearchTermsAnalyzer",
        version="unknown",
        finished_at=datetime.fromisoformat(timestamp),
    )

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
