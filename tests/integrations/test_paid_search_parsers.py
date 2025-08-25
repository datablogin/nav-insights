import json
from pathlib import Path
from nav_insights.integrations.paid_search.competitor_insights import parse_competitor_insights
from nav_insights.integrations.paid_search.keyword_analyzer import parse_keyword_analyzer
from nav_insights.integrations.paid_search.search_terms import parse_search_terms
from nav_insights.integrations.paid_search.placement_audit import parse_placement_audit
from nav_insights.core.ir_base import AuditFindings


def test_competitor_insights_smoke():
    sample = {
        "analyzer": "CompetitorInsightsAnalyzer",
        "customer_id": "123-456-7890",
        "analysis_period": {"start_date": "2025-07-01T00:00:00", "end_date": "2025-07-31T00:00:00"},
        "timestamp": "2025-08-24T12:00:00",
        "summary": {"priority_level": "MEDIUM"},
        "detailed_findings": {
            "primary_competitors": [
                {
                    "competitor": "Cracker Barrel",
                    "impression_share_overlap": 0.34,
                    "shared_keywords": 89,
                    "cost_competition_level": "HIGH",
                    "competitive_threat_level": "HIGH",
                }
            ]
        },
    }
    af = parse_competitor_insights(sample)
    assert isinstance(af, AuditFindings)
    assert af.findings


def test_keyword_analyzer_smoke():
    sample = {
        "analyzer": "KeywordAnalyzer",
        "customer_id": "123-456-7890",
        "analysis_period": {"start_date": "2025-07-01T00:00:00", "end_date": "2025-07-31T00:00:00"},
        "timestamp": "2025-08-24T12:00:00",
        "summary": {"priority_level": "CRITICAL"},
        "detailed_findings": {
            "underperforming_keywords": [
                {
                    "name": "food delivery",
                    "match_type": "BROAD",
                    "cost": 892.45,
                    "conversions": 0,
                    "cpa": "N/A",
                    "campaign": "Generic",
                    "recommendation": "Pause",
                }
            ],
            "top_performers": [
                {
                    "name": "brand term",
                    "match_type": "EXACT",
                    "cost": 234.56,
                    "conversions": 18,
                    "cpa": 13.03,
                    "campaign": "Brand",
                    "recommendation": "Increase bid",
                }
            ],
        },
    }
    af = parse_keyword_analyzer(sample)
    assert isinstance(af, AuditFindings)
    assert len(af.findings) == 2


def test_search_terms_smoke():
    sample = {
        "analyzer": "SearchTermsAnalyzer",
        "customer_id": "123-456-7890",
        "timestamp": "2025-08-24T12:00:00",
        "summary": {"priority_level": "HIGH"},
        "detailed_findings": {
            "wasteful_search_terms": [
                {
                    "term": "jobs",
                    "cost": 100.0,
                    "conversions": 0,
                    "clicks": 10,
                    "keyword_triggered": "brand",
                    "recommendation": "Add negative",
                }
            ],
            "negative_keyword_suggestions": [
                {
                    "negative_keyword": "free",
                    "match_type": "BROAD",
                    "estimated_savings": 500.0,
                    "reason": "free meal searches",
                }
            ],
        },
    }
    af = parse_search_terms(sample)
    assert isinstance(af, AuditFindings)
    assert len(af.findings) == 2


def test_placement_audit_smoke():
    sample = {
        "analyzer": "placement_audit",
        "customer_id": "123-456-7890",
        "analysis_period": {
            "start_date": "2025-07-01T00:00:00Z",
            "end_date": "2025-07-31T23:59:59Z",
        },
        "timestamp": "2025-08-24T15:30:00Z",
        "summary": {"priority_level": "HIGH"},
        "detailed_findings": {
            "poor_performers": [
                {
                    "placement_url": "example.com",
                    "network": "Display",
                    "cost": 245.67,
                    "conversions": 0,
                    "clicks": 123,
                    "impressions": 45678,
                    "ctr": 0.27,
                    "conversion_rate": 0.0,
                    "cpa": "N/A",
                    "campaign": "Display Campaign",
                    "ad_group": "General Display",
                    "recommendation": "Exclude placement - High cost with zero conversions",
                }
            ],
            "top_performers": [
                {
                    "placement_url": "youtube.com",
                    "network": "YouTube",
                    "cost": 1234.50,
                    "conversions": 45,
                    "clicks": 2340,
                    "impressions": 156789,
                    "ctr": 1.49,
                    "conversion_rate": 1.92,
                    "cpa": 27.43,
                    "campaign": "Video Campaign",
                    "ad_group": "YouTube Targeting",
                    "recommendation": "Excellent performance - Consider increasing bids or budget",
                }
            ],
        },
    }
    af = parse_placement_audit(sample)
    assert isinstance(af, AuditFindings)
    assert len(af.findings) == 2

    # Check findings categories and entities
    poor_finding = next(f for f in af.findings if "PLACEMENT_POOR" in f.id)
    top_finding = next(f for f in af.findings if "PLACEMENT_TOP" in f.id)

    assert poor_finding.category == "creative"
    assert top_finding.category == "creative"

    # Check entities are created correctly
    assert len(poor_finding.entities) == 3  # placement, campaign, ad_group
    assert any(e.type == "placement" for e in poor_finding.entities)
    assert any(e.type == "campaign" for e in poor_finding.entities)
    assert any(e.type == "ad_group" for e in poor_finding.entities)

    # Check metrics
    assert "cost" in poor_finding.metrics
    assert "conversions" in poor_finding.metrics
    assert "ctr" in poor_finding.metrics
    assert "cpa" not in poor_finding.metrics  # Should be omitted for N/A

    assert "cpa" in top_finding.metrics  # Should be present for valid value


def test_placement_audit_happy_path_fixture():
    """Test the happy path fixture validates correctly."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "placement_audit_happy_path.json"
    with open(fixture_path, "r") as f:
        data = json.load(f)

    af = parse_placement_audit(data)
    assert isinstance(af, AuditFindings)

    # Should have 2 poor performers + 2 top performers = 4 findings
    assert len(af.findings) == 4

    # Check account mapping
    assert af.account.account_id == "123-456-7890"

    # Check date range mapping
    assert af.date_range.start_date.isoformat() == "2025-07-01"
    assert af.date_range.end_date.isoformat() == "2025-07-31"

    # Check aggregates contain network distribution
    assert "networks" in af.aggregates

    # Check severity mapping
    poor_findings = [f for f in af.findings if "PLACEMENT_POOR" in f.id]
    assert all(f.severity == "high" for f in poor_findings)  # HIGH priority maps to high severity


def test_placement_audit_edge_case_fixture():
    """Test the edge case fixture handles problematic data correctly."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "placement_audit_edge_case.json"
    with open(fixture_path, "r") as f:
        data = json.load(f)

    af = parse_placement_audit(data)
    assert isinstance(af, AuditFindings)

    # Should have 2 poor performers + 1 top performer = 3 findings
    assert len(af.findings) == 3

    # Check URL sanitization
    finding_with_protocol = next((f for f in af.findings if "example-with-protocol" in f.id), None)
    assert finding_with_protocol is not None

    # Check special character handling
    finding_with_special_chars = next(
        (f for f in af.findings if "site-with-special-chars" in f.id), None
    )
    assert finding_with_special_chars is not None

    # Check empty/null value handling
    finding_with_empty_url = next(
        (f for f in af.findings if f.entities[0].name == "unknown_placement"), None
    )
    assert finding_with_empty_url is not None

    # Check network normalization
    search_partners_finding = next(
        (f for f in af.findings if f.dims.get("network") == "Search Partners"), None
    )
    assert search_partners_finding is not None

    gmail_finding = next((f for f in af.findings if f.dims.get("network") == "Gmail"), None)
    assert gmail_finding is not None


def test_placement_audit_rate_conversion():
    """Test that rate values are properly converted to [0,1] range."""
    sample = {
        "analyzer": "placement_audit",
        "customer_id": "test-rates",
        "analysis_period": {
            "start_date": "2025-07-01T00:00:00Z",
            "end_date": "2025-07-31T23:59:59Z",
        },
        "timestamp": "2025-08-24T15:30:00Z",
        "summary": {"priority_level": "MEDIUM"},
        "detailed_findings": {
            "poor_performers": [
                {
                    "placement_url": "test.com",
                    "network": "Display",
                    "cost": 100.0,
                    "conversions": 1,
                    "clicks": 50,
                    "impressions": 1000,
                    "ctr": 5.0,  # Percentage format (should be converted to 0.05)
                    "conversion_rate": 2.0,  # Percentage format (should be converted to 0.02)
                    "cpa": 100.0,
                    "campaign": "Test Campaign",
                    "ad_group": "Test Ad Group",
                    "recommendation": "Test",
                }
            ],
            "top_performers": [],
        },
    }

    af = parse_placement_audit(sample)
    finding = af.findings[0]

    # Check that percentage rates were converted to decimal
    assert finding.metrics["ctr"] == 0.05  # 5% -> 0.05
    assert finding.metrics["conversion_rate"] == 0.02  # 2% -> 0.02
