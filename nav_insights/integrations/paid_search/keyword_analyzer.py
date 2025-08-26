from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel

from ...core.ir_base import (
    AuditFindings,
    AccountMeta,
    DateRange,
    Evidence,
    AnalyzerProvenance,
    Finding,
)
from ...core import (
    ParserError,
    map_priority_level,
    generate_finding_id,
    validate_non_negative_metrics,
    safe_decimal_conversion,
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
    
    Raises:
        ParserError: If parsing fails due to invalid data
        CoreError: If validation fails
    """
    try:
        inp = KeywordAnalyzerInput.model_validate(data)
    except Exception as e:
        raise ParserError(
            "Failed to validate KeywordAnalyzer input data",
            parser_name="KeywordAnalyzer",
            original_error=e,
        )

    try:
        start = datetime.fromisoformat(inp.analysis_period["start_date"]).date()
        end = datetime.fromisoformat(inp.analysis_period["end_date"]).date()
    except Exception as e:
        raise ParserError(
            "Failed to parse analysis period dates",
            parser_name="KeywordAnalyzer",
            context={"analysis_period": inp.analysis_period},
            original_error=e,
        )

    account = AccountMeta(account_id=inp.customer_id)
    date_range = DateRange(start_date=start, end_date=end)

    findings: List[Finding] = []

    # Underperforming keywords → findings
    for item in inp.detailed_findings.get("underperforming_keywords", []) or []:
        name = str(item.get("name", "unknown"))
        match_type = str(item.get("match_type", ""))
        recommendation = item.get("recommendation")
        summary = f"Underperforming keyword '{name}' ({match_type})"
        severity = map_priority_level(inp.summary.get("priority_level"))
        
        # Validate and convert metrics with proper error handling
        raw_metrics = {
            "cost": item.get("cost", 0),
            "conversions": item.get("conversions", 0),
        }
        if (cpa := item.get("cpa")) not in (None, "N/A"):
            raw_metrics["cpa"] = cpa
        
        # Validate non-negative metrics
        validated_metrics = validate_non_negative_metrics(
            raw_metrics,
            ["cost", "conversions"],  # CPA can be calculated metric, may not need validation
            parser_name="KeywordAnalyzer",
        )
        
        # Add CPA if present
        if "cpa" in raw_metrics:
            validated_metrics["cpa"] = safe_decimal_conversion(
                raw_metrics["cpa"], "cpa"
            )
        
        # Generate unique finding ID
        finding_id = generate_finding_id("KW_UNDER", name, match_type)
        
        findings.append(
            Finding(
                id=finding_id,
                category="keywords",
                summary=summary,
                description=recommendation,
                severity=severity,
                dims={"match_type": match_type, "campaign": item.get("campaign")},
                metrics=validated_metrics,
            )
        )

    # Top performers → findings
    for item in inp.detailed_findings.get("top_performers", []) or []:
        name = str(item.get("name", "unknown"))
        match_type = str(item.get("match_type", ""))
        recommendation = item.get("recommendation")
        summary = f"Top performer '{name}' ({match_type})"
        severity = map_priority_level(inp.summary.get("priority_level"))
        
        # Validate and convert metrics with proper error handling
        raw_metrics = {
            "cost": item.get("cost", 0),
            "conversions": item.get("conversions", 0),
        }
        if (cpa := item.get("cpa")) is not None:
            raw_metrics["cpa"] = cpa
        
        # Validate non-negative metrics
        validated_metrics = validate_non_negative_metrics(
            raw_metrics,
            ["cost", "conversions"],
            parser_name="KeywordAnalyzer",
        )
        
        # Add CPA if present
        if "cpa" in raw_metrics:
            validated_metrics["cpa"] = safe_decimal_conversion(
                raw_metrics["cpa"], "cpa"
            )
        
        # Generate unique finding ID
        finding_id = generate_finding_id("KW_TOP", name, match_type)
        
        findings.append(
            Finding(
                id=finding_id,
                category="keywords",
                summary=summary,
                description=recommendation,
                severity=severity,
                dims={"match_type": match_type, "campaign": item.get("campaign")},
                metrics=validated_metrics,
            )
        )

    evidence = Evidence(source="paid_search_nav.keyword")
    
    try:
        finished_at = datetime.fromisoformat(inp.timestamp)
    except Exception as e:
        raise ParserError(
            "Failed to parse timestamp",
            parser_name="KeywordAnalyzer",
            context={"timestamp": inp.timestamp},
            original_error=e,
        )
    
    prov = AnalyzerProvenance(
        name=inp.analyzer,
        version="unknown",
        finished_at=finished_at,
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
