from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from pydantic import BaseModel

from ...core.findings_ir import (
    AuditFindings,
    AccountMeta,
    DateRange,
    Totals,
    Aggregates,
    Evidence,
    AnalyzerProvenance,
    Finding,
    Severity,
    EntityRef,
    EntityType,
)


class VideoCreativeInput(BaseModel):
    analyzer: str
    customer_id: str
    analysis_period: Dict[str, str]
    timestamp: str
    summary: Dict[str, Any]
    detailed_findings: Dict[str, Any]


def parse_video_creative(data: Dict[str, Any]) -> AuditFindings:
    """Parser mapping PaidSearchNav VideoCreative analyzer output to AuditFindings.
    
    Maps video creative performance data including poor and top performers with
    proper micro-to-USD conversions and video-specific metrics.

    See docs/mappings/paid_search/video_creative_to_ir.md for full mapping details.
    """
    inp = VideoCreativeInput.model_validate(data)

    start = datetime.fromisoformat(inp.analysis_period["start_date"]).date()
    end = datetime.fromisoformat(inp.analysis_period["end_date"]).date()

    account = AccountMeta(account_id=inp.customer_id)
    date_range = DateRange(start_date=start, end_date=end)

    findings: List[Finding] = []
    severity = _map_priority(inp.summary.get("priority_level"))

    # Poor performers → findings
    counter = 1
    for item in inp.detailed_findings.get("poor_performers", []) or []:
        creative_id = str(item.get("creative_id", "unknown"))
        creative_name = str(item.get("creative_name", "Unknown Creative"))
        if not creative_name.strip():
            creative_name = "Unknown Creative"
        
        # Create entities
        creative_entity = EntityRef(
            type=EntityType.other,
            id=f"creative:{creative_id}",
            name=creative_name
        )
        
        campaign_value = item.get("campaign")
        ad_group_value = item.get("ad_group")
        
        campaign_name = str(campaign_value) if campaign_value is not None else ""
        ad_group_name = str(ad_group_value) if ad_group_value is not None else ""
        
        entities = [creative_entity]
        
        if campaign_name and campaign_name.strip():
            entities.append(EntityRef(
                type=EntityType.campaign,
                id=f"cmp:{campaign_name}",
                name=campaign_name
            ))
            
        if ad_group_name and ad_group_name.strip():
            entities.append(EntityRef(
                type=EntityType.ad_group,
                id=f"adg:{ad_group_name}",
                name=ad_group_name
            ))

        # Build metrics with micro-to-USD conversions
        metrics = {}
        if "impressions" in item:
            metrics["impressions"] = Decimal(str(item["impressions"]))
        if "views" in item:
            metrics["views"] = Decimal(str(item["views"]))
        if "view_rate" in item:
            metrics["view_rate"] = Decimal(str(item["view_rate"]))
        if "cost_micros" in item:
            metrics["cost_usd"] = Decimal(str(item["cost_micros"])) / Decimal("1000000")
        if "conversions" in item:
            metrics["conversions"] = Decimal(str(item["conversions"]))
        if "performance_score" in item:
            metrics["performance_score"] = Decimal(str(item["performance_score"]))
        
        # Handle CPA - only include if not null/N/A
        cpa_micros = item.get("cpa_micros")
        if cpa_micros is not None and str(cpa_micros).upper() != "N/A":
            try:
                metrics["cpa_usd"] = Decimal(str(cpa_micros)) / Decimal("1000000")
            except (ValueError, TypeError):
                pass  # Skip invalid CPA values

        # Build dimensions
        dims = {}
        if "video_duration_seconds" in item:
            dims["video_duration_seconds"] = item["video_duration_seconds"]
        if campaign_name and campaign_name.strip():
            dims["campaign"] = campaign_name
        if ad_group_name and ad_group_name.strip():
            dims["ad_group"] = ad_group_name
        if "performance_score" in item:
            dims["performance_score"] = item["performance_score"]

        finding_id = f"poor_video_{counter}_{_sanitize_account_id(inp.customer_id)}"
        summary = f"Poor video creative: {creative_name}"
        recommendation = item.get("recommendation", "Review video creative performance")
        description = str(recommendation) if recommendation is not None else "Review video creative performance"

        findings.append(
            Finding(
                id=finding_id,
                category="creative",
                summary=summary,
                description=description,
                severity=severity,
                entities=entities,
                metrics=metrics,
                dims=dims,
                evidence=[
                    Evidence(
                        source="paid_search_nav.video_creative",
                        entities=[creative_entity]
                    )
                ]
            )
        )
        counter += 1

    # Top performers → findings (with low severity for positive findings)
    for item in inp.detailed_findings.get("top_performers", []) or []:
        creative_id = str(item.get("creative_id", "unknown"))
        creative_name = str(item.get("creative_name", "Unknown Creative"))
        if not creative_name.strip():
            creative_name = "Unknown Creative"
        
        # Create entities
        creative_entity = EntityRef(
            type=EntityType.other,
            id=f"creative:{creative_id}",
            name=creative_name
        )
        
        campaign_value = item.get("campaign")
        ad_group_value = item.get("ad_group")
        
        campaign_name = str(campaign_value) if campaign_value is not None else ""
        ad_group_name = str(ad_group_value) if ad_group_value is not None else ""
        
        entities = [creative_entity]
        
        if campaign_name and campaign_name.strip():
            entities.append(EntityRef(
                type=EntityType.campaign,
                id=f"cmp:{campaign_name}",
                name=campaign_name
            ))
            
        if ad_group_name and ad_group_name.strip():
            entities.append(EntityRef(
                type=EntityType.ad_group,
                id=f"adg:{ad_group_name}",
                name=ad_group_name
            ))

        # Build metrics with micro-to-USD conversions
        metrics = {}
        if "impressions" in item:
            metrics["impressions"] = Decimal(str(item["impressions"]))
        if "views" in item:
            metrics["views"] = Decimal(str(item["views"]))
        if "view_rate" in item:
            metrics["view_rate"] = Decimal(str(item["view_rate"]))
        if "cost_micros" in item:
            metrics["cost_usd"] = Decimal(str(item["cost_micros"])) / Decimal("1000000")
        if "conversions" in item:
            metrics["conversions"] = Decimal(str(item["conversions"]))
        if "performance_score" in item:
            metrics["performance_score"] = Decimal(str(item["performance_score"]))
        
        # Handle CPA - only include if not null/N/A
        cpa_micros = item.get("cpa_micros")
        if cpa_micros is not None and str(cpa_micros).upper() != "N/A":
            try:
                metrics["cpa_usd"] = Decimal(str(cpa_micros)) / Decimal("1000000")
            except (ValueError, TypeError):
                pass  # Skip invalid CPA values

        # Build dimensions
        dims = {}
        if "video_duration_seconds" in item:
            dims["video_duration_seconds"] = item["video_duration_seconds"]
        if campaign_name and campaign_name.strip():
            dims["campaign"] = campaign_name
        if ad_group_name and ad_group_name.strip():
            dims["ad_group"] = ad_group_name
        if "performance_score" in item:
            dims["performance_score"] = item["performance_score"]

        finding_id = f"top_video_{counter}_{_sanitize_account_id(inp.customer_id)}"
        summary = f"Top video creative: {creative_name}"
        recommendation = item.get("recommendation", "Continue high performance")
        description = str(recommendation) if recommendation is not None else "Continue high performance"

        findings.append(
            Finding(
                id=finding_id,
                category="creative",
                summary=summary,
                description=description,
                severity=Severity.low,  # Top performers have low severity (positive finding)
                entities=entities,
                metrics=metrics,
                dims=dims,
                evidence=[
                    Evidence(
                        source="paid_search_nav.video_creative",
                        entities=[creative_entity]
                    )
                ]
            )
        )
        counter += 1

    # Build totals with spend conversion
    totals = Totals()
    if "total_video_spend_micros" in inp.summary:
        spend_micros = inp.summary["total_video_spend_micros"]
        totals.spend_usd = Decimal(str(spend_micros)) / Decimal("1000000")

    # Build aggregates with video-specific metrics
    aggregates = Aggregates()
    video_metrics = {}
    summary_data = inp.summary
    
    if "total_video_creatives" in summary_data:
        video_metrics["total_video_creatives"] = Decimal(str(summary_data["total_video_creatives"]))
    if "poor_performers_count" in summary_data:
        video_metrics["poor_performers_count"] = Decimal(str(summary_data["poor_performers_count"]))
    if "top_performers_count" in summary_data:
        video_metrics["top_performers_count"] = Decimal(str(summary_data["top_performers_count"]))
    if "average_view_rate" in summary_data:
        video_metrics["average_view_rate"] = Decimal(str(summary_data["average_view_rate"]))

    # Create global evidence and provenance
    evidence = Evidence(
        source="paid_search_nav.video_creative",
        rows=len(findings)
    )
    prov = AnalyzerProvenance(
        name=inp.analyzer,
        version="unknown",
        finished_at=datetime.fromisoformat(inp.timestamp),
    )

    af = AuditFindings(
        account=account,
        date_range=date_range,
        totals=totals,
        aggregates=aggregates,
        findings=findings,
        data_sources=[evidence],
        analyzers=[prov],
    )

    # Add video metrics to index for easy access
    if video_metrics:
        af.index["video_metrics"] = video_metrics
    
    return af


def _map_priority(level: Any) -> Severity:
    """Map priority level to Severity enum.
    
    CRITICAL→high, HIGH→high, MEDIUM→medium, LOW→low
    """
    s = str(level or "").lower()
    if s in ("critical", "high"):
        return Severity.high
    if s == "medium":
        return Severity.medium
    return Severity.low


def _sanitize_account_id(account_id: str) -> str:
    """Sanitize account ID for use in finding IDs."""
    return account_id.replace("-", "_").replace(" ", "_")