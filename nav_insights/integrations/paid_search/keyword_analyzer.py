from __future__ import annotations
from datetime import datetime, timezone
import hashlib
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from pydantic import BaseModel
from ...core.errors import CoreError

from ...core.ir_base import (
    AuditFindings,
    AccountMeta,
    DateRange,
    Evidence,
    AnalyzerProvenance,
    Finding,
    Severity,
    EntityRef,
    Totals,
)
from .utils import map_priority_level


class KeywordAnalyzerInput(BaseModel):
    analyzer: str
    customer_id: str
    analysis_period: Dict[str, str]
    timestamp: str
    summary: Dict[str, Any]
    detailed_findings: Dict[str, Any]


def parse_keyword_analyzer(data: Dict[str, Any]) -> AuditFindings:
    """Parse PaidSearchNav KeywordAnalyzer output to Core IR AuditFindings.

    See docs/mappings/paid_search/keyword_analyzer_to_ir.md for full mapping details.
    """
    inp = KeywordAnalyzerInput.model_validate(data)

    try:
        start = datetime.fromisoformat(inp.analysis_period["start_date"]).date()
        end = datetime.fromisoformat(inp.analysis_period["end_date"]).date()
    except (KeyError, ValueError):
        # Fallback to timestamp-based date if analysis_period is malformed
        try:
            dt = datetime.fromisoformat(inp.timestamp)
            start = dt.date()
            end = dt.date()
        except ValueError:
            # Final fallback to current date
            dt = datetime.now(timezone.utc)
            start = dt.date()
            end = dt.date()

    account = AccountMeta(account_id=inp.customer_id)
    date_range = DateRange(start_date=start, end_date=end)

    findings: List[Finding] = []
    finding_counter = 0

    # Underperforming keywords → findings
    for item in inp.detailed_findings.get("underperforming_keywords", []) or []:
        finding_counter += 1
        name = str(item.get("name", "unknown")).strip() or "unknown"
        match_type = str(item.get("match_type", "UNKNOWN")).upper()
        campaign = str(item.get("campaign", "")).strip() or "Unknown Campaign"
        recommendation = item.get("recommendation") or "Review keyword performance"

        summary = f"Underperforming keyword '{name}' ({match_type})"
        severity = map_priority_level(inp.summary.get("priority_level"))

        # Build metrics, handling N/A values and ensuring non-negative values
        cost = Decimal(str(item.get("cost", 0)))
        conversions = Decimal(str(item.get("conversions", 0)))
        if cost < 0 or conversions < 0:
            raise CoreError(
                code="invalid_metric",
                category="parser.keyword",
                message="Cost and conversions must be non-negative",
                severity="error",
                context={"name": name, "cost": str(cost), "conversions": str(conversions)},
            )

        metrics: Dict[str, Decimal] = {
            "cost": cost,
            "conversions": conversions,
        }
        if (cpa := item.get("cpa")) not in (None, "N/A"):
            try:
                metrics["cpa"] = Decimal(str(cpa))
            except (InvalidOperation, ValueError):
                # Skip invalid CPA values (e.g., non-numeric strings)
                pass

        # Build entities according to spec
        entities = [
            EntityRef(type="keyword", id=f"kw:{name}", name=name),
            EntityRef(type="campaign", id=f"cmp:{campaign}", name=campaign),
        ]

        name_hash = hashlib.md5(name.encode()).hexdigest()[:8]
        findings.append(
            Finding(
                id=f"keyword_analyzer_{inp.customer_id}_under_{finding_counter}_{name[:15].replace(' ', '_')}_{name_hash}",
                category="keywords",
                summary=summary,
                description=recommendation,
                severity=severity,
                entities=entities,
                dims={"match_type": match_type, "campaign": campaign},
                metrics=metrics,
            )
        )

    # Top performers → findings (typically low severity as they're performing well)
    for item in inp.detailed_findings.get("top_performers", []) or []:
        finding_counter += 1
        name = str(item.get("name", "unknown")).strip() or "unknown"
        match_type = str(item.get("match_type", "UNKNOWN")).upper()
        campaign = str(item.get("campaign", "")).strip() or "Unknown Campaign"
        recommendation = item.get("recommendation") or "Continue monitoring performance"

        summary = f"Top performing keyword '{name}' ({match_type})"
        # Top performers typically have low severity since they're doing well
        severity = Severity.low

        # Build metrics
        cost = Decimal(str(item.get("cost", 0)))
        conversions = Decimal(str(item.get("conversions", 0)))
        if cost < 0 or conversions < 0:
            raise CoreError(
                code="invalid_metric",
                category="parser.keyword",
                message="Cost and conversions must be non-negative",
                severity="error",
                context={"name": name, "cost": str(cost), "conversions": str(conversions)},
            )

        metrics: Dict[str, Decimal] = {
            "cost": cost,
            "conversions": conversions,
        }
        if (cpa := item.get("cpa")) not in (None, "N/A"):
            try:
                metrics["cpa"] = Decimal(str(cpa))
            except (InvalidOperation, ValueError):
                # Skip invalid CPA values (e.g., non-numeric strings)
                pass

        # Build entities according to spec
        entities = [
            EntityRef(type="keyword", id=f"kw:{name}", name=name),
            EntityRef(type="campaign", id=f"cmp:{campaign}", name=campaign),
        ]

        name_hash = hashlib.md5(name.encode()).hexdigest()[:8]
        findings.append(
            Finding(
                id=f"keyword_analyzer_{inp.customer_id}_top_{finding_counter}_{name[:15].replace(' ', '_')}_{name_hash}",
                category="keywords",
                summary=summary,
                description=recommendation,
                severity=severity,
                entities=entities,
                dims={"match_type": match_type, "campaign": campaign},
                metrics=metrics,
            )
        )

    # Build index summary from summary data (Aggregates does not allow arbitrary keys)
    index = {}
    if inp.summary:
        index["keyword_summary"] = {
            "total_analyzed": inp.summary.get("total_keywords_analyzed", 0),
            "recommendations_count": inp.summary.get("recommendations_count", 0),
            "potential_monthly_savings": float(inp.summary.get("potential_monthly_savings", 0)),
            "priority_level": inp.summary.get("priority_level", "UNKNOWN"),
        }

    evidence = Evidence(source="paid_search_nav.keyword")

    try:
        finished_at = datetime.fromisoformat(inp.timestamp)
    except ValueError:
        # Fallback to current time if timestamp is malformed
        finished_at = datetime.now(timezone.utc)

    prov = AnalyzerProvenance(
        name=inp.analyzer,
        version="1.0.0",  # Version from the KeywordAnalyzer implementation
        finished_at=finished_at,
    )

    af = AuditFindings(
        account=account,
        date_range=date_range,
        totals=Totals(),
        findings=findings,
        data_sources=[evidence],
        analyzers=[prov],
        index=index,
    )
    return af
