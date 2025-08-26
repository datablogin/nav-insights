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
    
    Raises:
        ParserError: If parsing fails due to invalid data
        CoreError: If validation fails
    """
    try:
        inp = SearchTermsInput.model_validate(data)
    except Exception as e:
        raise ParserError(
            "Failed to validate SearchTerms input data",
            parser_name="SearchTermsAnalyzer",
            original_error=e,
        )

    # Fallbacks if some headers missing (Topgolf sample shape differs)
    customer_id = inp.customer_id or str(
        data.get("customer_id") or data.get("account_id") or "unknown"
    )
    timestamp = inp.timestamp or str(data.get("timestamp") or datetime.utcnow().isoformat())

    try:
        if inp.analysis_period:
            start = datetime.fromisoformat(inp.analysis_period["start_date"]).date()
            end = datetime.fromisoformat(inp.analysis_period["end_date"]).date()
        else:
            # derive a dummy window if not present
            dt = datetime.fromisoformat(timestamp)
            start = dt.date()
            end = dt.date()
    except Exception as e:
        raise ParserError(
            "Failed to parse dates",
            parser_name="SearchTermsAnalyzer",
            context={"analysis_period": inp.analysis_period, "timestamp": timestamp},
            original_error=e,
        )

    account = AccountMeta(account_id=customer_id)
    date_range = DateRange(start_date=start, end_date=end)

    findings: List[Finding] = []

    # Wasteful search terms
    for item in inp.detailed_findings.get("wasteful_search_terms") or []:
        term = str(item.get("term", ""))
        kw = item.get("keyword_triggered")
        summary = f"Wasteful search term '{term}' — add negative"
        severity = map_priority_level(inp.summary.get("priority_level") if inp.summary else None)
        
        # Validate and convert metrics
        raw_metrics = {
            "cost": item.get("cost", 0),
            "conversions": item.get("conversions", 0),
            "clicks": item.get("clicks", 0),
        }
        
        # Validate non-negative metrics
        validated_metrics = validate_non_negative_metrics(
            raw_metrics,
            ["cost", "conversions", "clicks"],
            parser_name="SearchTermsAnalyzer",
        )
        
        # Generate unique finding ID
        finding_id = generate_finding_id("ST_WASTE", term)
        
        findings.append(
            Finding(
                id=finding_id,
                category="keywords",
                summary=summary,
                description=item.get("recommendation"),
                severity=severity,
                dims={"keyword_triggered": kw} if kw else {},
                metrics=validated_metrics,
            )
        )

    # Negative keyword suggestions
    for item in inp.detailed_findings.get("negative_keyword_suggestions") or []:
        neg = str(item.get("negative_keyword", ""))
        summary = f"Negative keyword suggestion '{neg}'"
        severity = map_priority_level(inp.summary.get("priority_level") if inp.summary else None)
        
        # Validate and convert metrics
        raw_metrics = {
            "estimated_savings_usd": item.get("estimated_savings", 0),
        }
        
        # Validate non-negative metrics
        validated_metrics = validate_non_negative_metrics(
            raw_metrics,
            ["estimated_savings_usd"],
            parser_name="SearchTermsAnalyzer",
        )
        
        # Generate unique finding ID
        finding_id = generate_finding_id("ST_NEG", neg)
        
        findings.append(
            Finding(
                id=finding_id,
                category="keywords",
                summary=summary,
                description=item.get("reason"),
                severity=severity,
                dims={"match_type": item.get("match_type")},
                metrics=validated_metrics,
            )
        )

    evidence = Evidence(source="paid_search_nav.search_terms")
    
    try:
        finished_at = datetime.fromisoformat(timestamp)
    except Exception as e:
        raise ParserError(
            "Failed to parse timestamp",
            parser_name="SearchTermsAnalyzer",
            context={"timestamp": timestamp},
            original_error=e,
        )
    
    prov = AnalyzerProvenance(
        name=inp.analyzer or "SearchTermsAnalyzer",
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
