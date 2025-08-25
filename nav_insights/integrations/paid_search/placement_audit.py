from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from pydantic import BaseModel

from ...core.ir_base import (
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


class PlacementAuditInput(BaseModel):
    analyzer: str
    customer_id: str
    analysis_period: Dict[str, str]
    timestamp: str
    summary: Dict[str, Any]
    detailed_findings: Dict[str, Any]


def parse_placement_audit(data: Dict[str, Any]) -> AuditFindings:
    """Parser mapping PaidSearchNav PlacementAudit output to AuditFindings.

    See docs/mappings/paid_search/placement_audit_to_ir.md for full mapping details.
    """
    inp = PlacementAuditInput.model_validate(data)

    start = datetime.fromisoformat(inp.analysis_period["start_date"]).date()
    end = datetime.fromisoformat(inp.analysis_period["end_date"]).date()

    account = AccountMeta(account_id=inp.customer_id)
    date_range = DateRange(start_date=start, end_date=end)

    findings: List[Finding] = []

    # Poor performers → findings
    for item in inp.detailed_findings.get("poor_performers", []) or []:
        placement_url = str(item.get("placement_url") or "unknown_placement")
        network = _normalize_network(item.get("network", ""))
        campaign = str(item.get("campaign") or "")
        ad_group = str(item.get("ad_group") or "")
        recommendation = item.get("recommendation", "")

        summary = f"Poor performing placement '{placement_url}'"
        severity = _map_priority(inp.summary.get("priority_level"))

        metrics: Dict[str, Decimal] = {
            "cost": Decimal(str(item.get("cost", 0) or 0)),
            "conversions": Decimal(str(item.get("conversions", 0) or 0)),
            "clicks": Decimal(str(item.get("clicks", 0) or 0)),
            "impressions": Decimal(str(item.get("impressions", 0) or 0)),
        }

        # Handle rate conversions - ensure they're in [0,1] range
        if (ctr := item.get("ctr")) is not None:
            try:
                ctr_val = float(ctr)
                # If CTR appears to be a percentage (>1), convert to decimal
                if ctr_val > 1:
                    ctr_val = ctr_val / 100
                metrics["ctr"] = Decimal(str(ctr_val))
            except (ValueError, TypeError):
                pass  # Skip invalid CTR values

        if (conversion_rate := item.get("conversion_rate")) is not None:
            try:
                cr_val = float(conversion_rate)
                # If conversion rate appears to be a percentage (>1), convert to decimal
                if cr_val > 1:
                    cr_val = cr_val / 100
                metrics["conversion_rate"] = Decimal(str(cr_val))
            except (ValueError, TypeError):
                pass  # Skip invalid conversion rate values

        # Handle CPA - omit if N/A
        if (cpa := item.get("cpa")) not in (None, "N/A"):
            try:
                metrics["cpa"] = Decimal(str(cpa))
            except (ValueError, TypeError):
                pass  # Omit invalid CPA values

        entities = [
            EntityRef(
                type=EntityType.placement, id=f"placement:{placement_url}", name=placement_url
            ),
            EntityRef(type=EntityType.campaign, id=f"cmp:{campaign}", name=campaign),
            EntityRef(type=EntityType.ad_group, id=f"adg:{ad_group}", name=ad_group),
        ]

        findings.append(
            Finding(
                id=f"PLACEMENT_POOR_{_sanitize_id(placement_url)}",
                category="creative",
                summary=summary,
                description=recommendation,
                severity=severity,
                entities=entities,
                dims={"network": network, "campaign": campaign, "ad_group": ad_group},
                metrics=metrics,
            )
        )

    # Top performers → findings
    for item in inp.detailed_findings.get("top_performers", []) or []:
        placement_url = str(item.get("placement_url") or "unknown_placement")
        network = _normalize_network(item.get("network", ""))
        campaign = str(item.get("campaign") or "")
        ad_group = str(item.get("ad_group") or "")
        recommendation = item.get("recommendation", "")

        summary = f"Top performing placement '{placement_url}'"
        severity = Severity.low  # Top performers are typically informational

        metrics: Dict[str, Decimal] = {
            "cost": Decimal(str(item.get("cost", 0) or 0)),
            "conversions": Decimal(str(item.get("conversions", 0) or 0)),
            "clicks": Decimal(str(item.get("clicks", 0) or 0)),
            "impressions": Decimal(str(item.get("impressions", 0) or 0)),
        }

        # Handle rate conversions
        if (ctr := item.get("ctr")) is not None:
            try:
                ctr_val = float(ctr)
                if ctr_val > 1:
                    ctr_val = ctr_val / 100
                metrics["ctr"] = Decimal(str(ctr_val))
            except (ValueError, TypeError):
                pass  # Skip invalid CTR values

        if (conversion_rate := item.get("conversion_rate")) is not None:
            try:
                cr_val = float(conversion_rate)
                if cr_val > 1:
                    cr_val = cr_val / 100
                metrics["conversion_rate"] = Decimal(str(cr_val))
            except (ValueError, TypeError):
                pass  # Skip invalid conversion rate values

        # Handle CPA - omit if N/A
        if (cpa := item.get("cpa")) not in (None, "N/A"):
            try:
                metrics["cpa"] = Decimal(str(cpa))
            except (ValueError, TypeError):
                pass  # Omit invalid CPA values

        entities = [
            EntityRef(
                type=EntityType.placement, id=f"placement:{placement_url}", name=placement_url
            ),
            EntityRef(type=EntityType.campaign, id=f"cmp:{campaign}", name=campaign),
            EntityRef(type=EntityType.ad_group, id=f"adg:{ad_group}", name=ad_group),
        ]

        findings.append(
            Finding(
                id=f"PLACEMENT_TOP_{_sanitize_id(placement_url)}",
                category="creative",
                summary=summary,
                description=recommendation,
                severity=severity,
                entities=entities,
                dims={"network": network, "campaign": campaign, "ad_group": ad_group},
                metrics=metrics,
            )
        )

    # Create evidence and provenance
    evidence = Evidence(source="paid_search_nav.placement_audit")
    prov = AnalyzerProvenance(
        name=inp.analyzer,
        version="1.0.0",  # TODO: Make configurable
        finished_at=datetime.fromisoformat(inp.timestamp),
    )

    # Build aggregates with network distribution if we have placement data
    aggregates_dict = {}
    if findings:
        network_counts = {}
        total_cost = Decimal("0")

        for finding in findings:
            network = finding.dims.get("network", "unknown")
            network_counts[network] = network_counts.get(network, 0) + 1
            total_cost += finding.metrics.get("cost", Decimal("0"))

        # Convert counts to percentages for network distribution
        # TODO: Add networks field to Aggregates class
        # total_placements = sum(network_counts.values())
        # if total_placements > 0:
        #     network_pct = {
        #         f"{network.lower()}_pct": Decimal(str(count / total_placements))
        #         for network, count in network_counts.items()
        #     }
        #     aggregates_dict["networks"] = network_pct

    af = AuditFindings(
        account=account,
        date_range=date_range,
        totals=Totals(),  # Use default empty totals
        aggregates=Aggregates(**aggregates_dict),
        findings=findings,
        data_sources=[evidence],
        analyzers=[prov],
    )
    return af


def _map_priority(level: Any) -> Severity:
    """Map priority level string to Severity enum."""
    s = str(level or "").lower()
    if s in ("critical", "high"):
        return Severity.high
    if s == "medium":
        return Severity.medium
    return Severity.low


def _normalize_network(network: str) -> str:
    """Normalize network names to standard values."""
    network_map = {
        "display": "Display",
        "youtube": "YouTube",
        "gmail": "Gmail",
        "apps": "Apps",
        "search partners": "Search Partners",
        "search_partners": "Search Partners",
    }
    normalized = network_map.get(str(network).lower().strip(), network)
    return normalized if normalized else "Unknown"


def _sanitize_id(placement_url: str) -> str:
    """Sanitize placement URL for use in Finding IDs."""
    # Remove protocol and common prefixes, limit length
    sanitized = placement_url.replace("https://", "").replace("http://", "").replace("www.", "")
    # Replace special characters with underscores for valid IDs
    sanitized = "".join(c if c.isalnum() or c in ".-" else "_" for c in sanitized)
    # Limit length to prevent excessively long IDs
    return sanitized[:50]
