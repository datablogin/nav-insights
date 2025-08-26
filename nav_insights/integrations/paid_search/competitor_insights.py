from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from pydantic import BaseModel

from ...core.findings_ir import (
    AuditFindings,
    AccountMeta,
    DateRange,
    Evidence,
    AnalyzerProvenance,
    Finding,
    Severity,
    EntityRef,
    EntityType,
    Totals,
)


class CompetitorInsightsInput(BaseModel):
    analyzer: str
    customer_id: str
    analysis_period: Dict[str, str]
    timestamp: str
    summary: Dict[str, Any]
    detailed_findings: Dict[str, Any]


def parse_competitor_insights(data: Dict[str, Any]) -> AuditFindings:
    """Parser mapping PaidSearchNav CompetitorInsightsAnalyzer output to AuditFindings.

    Maps both primary_competitors and keyword_gaps to individual findings with
    proper EntityRef objects, complete metrics, and structured evidence.

    See docs/mappings/paid_search/competitor_insights_to_ir.md for full mapping details.
    """
    inp = CompetitorInsightsInput.model_validate(data)

    start = datetime.fromisoformat(inp.analysis_period["start_date"]).date()
    end = datetime.fromisoformat(inp.analysis_period["end_date"]).date()

    account = AccountMeta(account_id=inp.customer_id)
    date_range = DateRange(start_date=start, end_date=end)

    findings: List[Finding] = []
    severity = _map_priority(inp.summary.get("priority_level"))

    # Primary competitors → one finding per item
    for item in inp.detailed_findings.get("primary_competitors", []) or []:
        competitor = str(item.get("competitor", "unknown"))
        competitor_clean = _sanitize_id(competitor)

        # Create competitor entity
        competitor_entity = EntityRef(
            type=EntityType.other, id=f"competitor:{competitor_clean}", name=competitor
        )

        # Build metrics
        metrics = {}
        if "impression_share_overlap" in item:
            metrics["impression_share_overlap"] = Decimal(str(item["impression_share_overlap"]))
        if "average_position_vs_you" in item:
            metrics["average_position_vs_you"] = Decimal(str(item["average_position_vs_you"]))
        if "shared_keywords" in item:
            metrics["shared_keywords"] = Decimal(str(item["shared_keywords"]))
        if "monthly_search_volume" in item:
            metrics["monthly_search_volume"] = Decimal(str(item["monthly_search_volume"]))

        # Build dimensions
        dims = {}
        if "cost_competition_level" in item:
            dims["cost_competition_level"] = item["cost_competition_level"]
        if "competitive_threat_level" in item:
            dims["competitive_threat_level"] = item["competitive_threat_level"]

        # Use opportunity text as description if available
        description = item.get("opportunity", "")

        findings.append(
            Finding(
                id=f"COMPETITOR_{competitor_clean}",
                category="other",  # fallback until competition category is added
                summary=f"Competitor overlap: {competitor}",
                description=description,
                severity=severity,
                entities=[competitor_entity],
                metrics=metrics,
                dims=dims,
                evidence=[
                    Evidence(
                        source="paid_search_nav.competitor_insights", entities=[competitor_entity]
                    )
                ],
            )
        )

    # Keyword gaps → one finding per gap
    for gap in inp.detailed_findings.get("keyword_gaps", []) or []:
        keyword = str(gap.get("keyword", "unknown"))
        keyword_clean = _sanitize_id(keyword)
        competitor_using = gap.get("competitor_using", [])

        # Create keyword entity
        keyword_entity = EntityRef(type=EntityType.keyword, id=f"kw:{keyword_clean}", name=keyword)

        # Create entities for competitors using this keyword
        entities = [keyword_entity]
        for comp in competitor_using:
            comp_clean = _sanitize_id(str(comp))
            entities.append(
                EntityRef(type=EntityType.other, id=f"competitor:{comp_clean}", name=str(comp))
            )

        # Build metrics
        metrics = {}
        if "search_volume" in gap:
            metrics["search_volume"] = Decimal(str(gap["search_volume"]))
        if "estimated_cpc" in gap:
            metrics["estimated_cpc"] = Decimal(str(gap["estimated_cpc"]))

        # Build dimensions
        dims = {}
        if "competition" in gap:
            dims["competition"] = gap["competition"]
        if competitor_using:
            dims["competitor_list"] = competitor_using

        # Create summary
        competitor_count = len(competitor_using)
        competitor_text = "competitor" if competitor_count == 1 else "competitors"
        summary = f"Gap: '{keyword}' used by {competitor_count} {competitor_text}"

        # Use recommendation as description
        description = gap.get("recommendation", "")

        findings.append(
            Finding(
                id=f"KEYWORD_GAP_{keyword_clean}",
                category="other",  # fallback until competition category is added
                summary=summary,
                description=description,
                severity=severity,
                entities=entities,
                metrics=metrics,
                dims=dims,
                evidence=[
                    Evidence(source="paid_search_nav.competitor_insights", entities=entities)
                ],
            )
        )

    # Store high-level summary metrics in custom analyzer fields
    competition_metrics = {}
    summary_data = inp.summary
    if summary_data:
        if "opportunity_score" in summary_data:
            competition_metrics["opportunity_score"] = Decimal(
                str(summary_data["opportunity_score"])
            )
        if "potential_monthly_savings" in summary_data:
            competition_metrics["potential_monthly_savings"] = Decimal(
                str(summary_data["potential_monthly_savings"])
            )
        if "competitors_identified" in summary_data:
            competition_metrics["competitors_identified"] = Decimal(
                str(summary_data["competitors_identified"])
            )
        if "keyword_overlap_detected" in summary_data:
            competition_metrics["keyword_overlap_detected"] = Decimal(
                str(summary_data["keyword_overlap_detected"])
            )

    # Create global evidence and provenance
    evidence = Evidence(source="paid_search_nav.competitor_insights", rows=len(findings))
    prov = AnalyzerProvenance(
        name=inp.analyzer,
        version="unknown",
        finished_at=datetime.fromisoformat(inp.timestamp),
    )

    af = AuditFindings(
        account=account,
        date_range=date_range,
        totals=Totals(),  # use defaults
        findings=findings,
        data_sources=[evidence],
        analyzers=[prov],
    )

    # Add custom competition metrics to the index field for easy access
    if competition_metrics:
        af.index["competition"] = competition_metrics
    return af


def _map_priority(level: Any) -> Severity:
    """Map priority level to Severity enum.

    CRITICAL→high, HIGH→high, MEDIUM→medium, LOW→low
    """
    s = str(level or "").lower()
    if s in ("critical", "high"):  # map CRITICAL→high
        return Severity.high
    if s == "medium":
        return Severity.medium
    return Severity.low


def _sanitize_id(text: str) -> str:
    """Sanitize text for use in entity IDs by replacing spaces and special chars."""
    import re

    return re.sub(r"[^a-zA-Z0-9_-]", "_", text.strip())
