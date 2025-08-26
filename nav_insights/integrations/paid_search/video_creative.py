from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Tuple
import hashlib

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


def _validate_numeric_ranges(item: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and clamp numeric values to expected ranges."""
    validated_item = item.copy()
    
    # Validate view_rate is in [0,1] range
    if "view_rate" in validated_item:
        try:
            view_rate = float(validated_item["view_rate"])
            if view_rate < 0 or view_rate > 1:
                # Log warning in production, for now just clamp
                validated_item["view_rate"] = max(0, min(1, view_rate))
        except (ValueError, TypeError):
            validated_item["view_rate"] = 0
    
    # Validate performance_score is in [0,1] range  
    if "performance_score" in validated_item:
        try:
            perf_score = float(validated_item["performance_score"])
            if perf_score < 0 or perf_score > 1:
                validated_item["performance_score"] = max(0, min(1, perf_score))
        except (ValueError, TypeError):
            validated_item["performance_score"] = 0
    
    return validated_item


def _extract_creative_info(item: Dict[str, Any]) -> Tuple[str, str]:
    """Extract and validate creative ID and name from item."""
    creative_id = str(item.get("creative_id", "unknown"))
    creative_name = str(item.get("creative_name", "Unknown Creative"))
    
    if not creative_name.strip():
        creative_name = "Unknown Creative"
    
    return creative_id, creative_name


def _build_entities(creative_id: str, creative_name: str, item: Dict[str, Any]) -> List[EntityRef]:
    """Build EntityRef objects for creative, campaign, and ad group."""
    # Create creative entity
    creative_entity = EntityRef(
        type=EntityType.other,
        id=f"creative:{creative_id}",
        name=creative_name
    )
    
    entities = [creative_entity]
    
    # Handle campaign and ad group entities
    campaign_value = item.get("campaign")
    ad_group_value = item.get("ad_group")
    
    campaign_name = str(campaign_value) if campaign_value is not None else ""
    ad_group_name = str(ad_group_value) if ad_group_value is not None else ""
    
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
    
    return entities


def _build_metrics(item: Dict[str, Any]) -> Dict[str, Decimal]:
    """Build metrics dictionary with micro-to-USD conversions and validation."""
    metrics = {}
    
    # Standard metrics
    metric_fields = ["impressions", "views", "conversions", "performance_score"]
    for field in metric_fields:
        if field in item:
            try:
                metrics[field] = Decimal(str(item[field]))
            except (ValueError, TypeError):
                metrics[field] = Decimal("0")
    
    # View rate with validation
    if "view_rate" in item:
        try:
            view_rate = Decimal(str(item["view_rate"]))
            # Ensure it's in [0,1] range
            if view_rate < 0 or view_rate > 1:
                view_rate = max(Decimal("0"), min(Decimal("1"), view_rate))
            metrics["view_rate"] = view_rate
        except (ValueError, TypeError):
            metrics["view_rate"] = Decimal("0")
    
    # Micro-to-USD conversions
    if "cost_micros" in item:
        try:
            cost_micros = Decimal(str(item["cost_micros"]))
            metrics["cost_usd"] = cost_micros / Decimal("1000000")
        except (ValueError, TypeError):
            pass  # Skip invalid cost values
    
    # Handle CPA - only include if not null/N/A
    cpa_micros = item.get("cpa_micros")
    if cpa_micros is not None and str(cpa_micros).upper() != "N/A":
        try:
            cpa_value = Decimal(str(cpa_micros))
            metrics["cpa_usd"] = cpa_value / Decimal("1000000")
        except (ValueError, TypeError):
            pass  # Skip invalid CPA values
    
    return metrics


def _build_dimensions(item: Dict[str, Any]) -> Dict[str, Any]:
    """Build dimensions dictionary."""
    dims = {}
    
    # Direct fields
    if "video_duration_seconds" in item:
        dims["video_duration_seconds"] = item["video_duration_seconds"]
    if "performance_score" in item:
        dims["performance_score"] = item["performance_score"]
    
    # Campaign and ad group (only if they exist and are non-empty)
    campaign_value = item.get("campaign")
    ad_group_value = item.get("ad_group")
    
    campaign_name = str(campaign_value) if campaign_value is not None else ""
    ad_group_name = str(ad_group_value) if ad_group_value is not None else ""
    
    if campaign_name and campaign_name.strip():
        dims["campaign"] = campaign_name
    if ad_group_name and ad_group_name.strip():
        dims["ad_group"] = ad_group_name
    
    return dims


def _generate_finding_id(finding_type: str, counter: int, customer_id: str, date_range: DateRange) -> str:
    """Generate collision-resistant finding ID with date range hash."""
    # Create a hash from date range to prevent collisions across different time periods
    date_hash_input = f"{date_range.start_date.isoformat()}_{date_range.end_date.isoformat()}"
    date_hash = hashlib.md5(date_hash_input.encode()).hexdigest()[:8]
    
    sanitized_account = _sanitize_account_id(customer_id)
    return f"{finding_type}_{counter}_{sanitized_account}_{date_hash}"


def _build_creative_finding(
    item: Dict[str, Any], 
    finding_type: str, 
    counter: int, 
    customer_id: str,
    date_range: DateRange,
    severity: Severity,
    default_recommendation: str
) -> Finding:
    """Build a Finding object for video creative data (poor or top performer)."""
    # Validate input data
    validated_item = _validate_numeric_ranges(item)
    
    # Extract creative info
    creative_id, creative_name = _extract_creative_info(validated_item)
    
    # Build components
    entities = _build_entities(creative_id, creative_name, validated_item)
    metrics = _build_metrics(validated_item)
    dims = _build_dimensions(validated_item)
    
    # Generate finding details
    finding_id = _generate_finding_id(finding_type, counter, customer_id, date_range)
    
    if finding_type.startswith("poor"):
        summary = f"Poor video creative: {creative_name}"
        used_severity = severity
    else:  # top performer
        summary = f"Top video creative: {creative_name}"
        used_severity = Severity.low  # Top performers always have low severity
    
    recommendation = validated_item.get("recommendation", default_recommendation)
    description = str(recommendation) if recommendation is not None else default_recommendation
    
    # Get creative entity for evidence
    creative_entity = next(e for e in entities if e.type == EntityType.other)
    
    return Finding(
        id=finding_id,
        category="creative",
        summary=summary,
        description=description,
        severity=used_severity,
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

    # Process poor performers and top performers using shared logic
    counter = 1
    
    # Poor performers → findings
    for item in inp.detailed_findings.get("poor_performers", []) or []:
        finding = _build_creative_finding(
            item=item,
            finding_type="poor_video",
            counter=counter,
            customer_id=inp.customer_id,
            date_range=date_range,
            severity=severity,
            default_recommendation="Review video creative performance"
        )
        findings.append(finding)
        counter += 1

    # Top performers → findings (with low severity for positive findings)
    for item in inp.detailed_findings.get("top_performers", []) or []:
        finding = _build_creative_finding(
            item=item,
            finding_type="top_video",
            counter=counter,
            customer_id=inp.customer_id,
            date_range=date_range,
            severity=severity,  # Will be overridden to low in the helper function
            default_recommendation="Continue high performance"
        )
        findings.append(finding)
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