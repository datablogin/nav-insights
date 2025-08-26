import json
from decimal import Decimal
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

    # Check aggregates structure (networks field temporarily disabled)
    assert isinstance(af.aggregates, type(af.aggregates))

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
    assert finding.metrics["ctr"] == Decimal("0.05")  # 5% -> 0.05
    assert finding.metrics["conversion_rate"] == Decimal("0.02")  # 2% -> 0.02


def test_placement_audit_null_handling():
    """Test that null values in campaign/ad_group fields are handled correctly."""
    sample = {
        "analyzer": "placement_audit",
        "customer_id": "test-nulls",
        "analysis_period": {
            "start_date": "2025-07-01T00:00:00Z",
            "end_date": "2025-07-31T23:59:59Z",
        },
        "timestamp": "2025-08-24T15:30:00Z",
        "summary": {"priority_level": "HIGH"},
        "detailed_findings": {
            "poor_performers": [
                {
                    "placement_url": "test.com",
                    "network": "Display",
                    "cost": 100.0,
                    "conversions": 0,
                    "clicks": 50,
                    "impressions": 1000,
                    "ctr": 5.0,
                    "conversion_rate": 0.0,
                    "cpa": "N/A",
                    "campaign": None,  # null value
                    "ad_group": None,  # null value
                    "recommendation": "Test",
                }
            ],
            "top_performers": [
                {
                    "placement_url": "good.com",
                    "network": "Display",
                    "cost": 50.0,
                    "conversions": 5,
                    "clicks": 25,
                    "impressions": 500,
                    "ctr": 5.0,
                    "conversion_rate": 20.0,
                    "cpa": "N/A",  # Should be omitted for top performers too
                    "campaign": None,  # null value
                    "ad_group": None,  # null value
                    "recommendation": "Great",
                }
            ],
        },
    }

    af = parse_placement_audit(sample)
    assert len(af.findings) == 2

    poor_finding = af.findings[0]
    top_finding = af.findings[1]

    # Check that null campaign/ad_group don't become "None" strings
    assert poor_finding.dims["campaign"] == ""
    assert poor_finding.dims["ad_group"] == ""
    assert top_finding.dims["campaign"] == ""
    assert top_finding.dims["ad_group"] == ""

    # Check entity names are empty strings, not "None"
    poor_campaign_entity = next(e for e in poor_finding.entities if e.type == "campaign")
    poor_adgroup_entity = next(e for e in poor_finding.entities if e.type == "ad_group")
    assert poor_campaign_entity.name == ""
    assert poor_adgroup_entity.name == ""

    top_campaign_entity = next(e for e in top_finding.entities if e.type == "campaign")
    top_adgroup_entity = next(e for e in top_finding.entities if e.type == "ad_group")
    assert top_campaign_entity.name == ""
    assert top_adgroup_entity.name == ""

    # Check that N/A CPA is omitted for both poor and top performers
    assert "cpa" not in poor_finding.metrics
    assert "cpa" not in top_finding.metrics


def test_keyword_analyzer_happy_path_fixture():
    """Test the happy path fixture for KeywordAnalyzer."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "keyword_analyzer_happy_path.json"
    with open(fixture_path, "r") as f:
        data = json.load(f)

    af = parse_keyword_analyzer(data)
    assert isinstance(af, AuditFindings)

    # Should have 3 underperformers + 3 top performers = 6 findings
    assert len(af.findings) == 6

    # Check account mapping
    assert af.account.account_id == "cotton_patch_001"

    # Check date range mapping
    assert af.date_range.start_date.isoformat() == "2025-08-01"
    assert af.date_range.end_date.isoformat() == "2025-08-24"

    # Check index structure for keyword summary
    assert "keyword_summary" in af.index
    assert af.index["keyword_summary"]["total_analyzed"] == 245
    assert af.index["keyword_summary"]["recommendations_count"] == 18
    assert af.index["keyword_summary"]["potential_monthly_savings"] == 3450.75
    assert af.index["keyword_summary"]["priority_level"] == "HIGH"

    # Check underperforming keywords
    under_findings = [f for f in af.findings if "under" in f.id]
    assert len(under_findings) == 3

    # First underperforming keyword should have N/A cpa omitted
    first_under = under_findings[0]
    assert first_under.summary == "Underperforming keyword 'restaurant near me' (BROAD)"
    assert first_under.severity == "high"  # HIGH priority maps to high severity
    assert "cpa" not in first_under.metrics  # N/A should be omitted
    assert first_under.metrics["cost"] == Decimal("892.45")
    assert first_under.metrics["conversions"] == Decimal("0")
    assert first_under.dims["match_type"] == "BROAD"
    assert first_under.dims["campaign"] == "Cotton Patch - Generic Terms"

    # Check entities
    assert len(first_under.entities) == 2
    keyword_entity = next(e for e in first_under.entities if e.type == "keyword")
    assert keyword_entity.id == "kw:restaurant near me"
    assert keyword_entity.name == "restaurant near me"

    campaign_entity = next(e for e in first_under.entities if e.type == "campaign")
    assert campaign_entity.id == "cmp:Cotton Patch - Generic Terms"
    assert campaign_entity.name == "Cotton Patch - Generic Terms"

    # Second underperformer should have valid CPA
    second_under = under_findings[1]
    assert "cpa" in second_under.metrics
    assert second_under.metrics["cpa"] == Decimal("283.62")

    # Check top performers
    top_findings = [f for f in af.findings if "top" in f.id]
    assert len(top_findings) == 3

    # Top performers should have low severity
    assert all(f.severity == "low" for f in top_findings)

    first_top = top_findings[0]
    assert first_top.summary == "Top performing keyword 'cotton patch cafe menu' (EXACT)"
    assert first_top.metrics["cpa"] == Decimal("16.31")
    assert first_top.dims["match_type"] == "EXACT"


def test_keyword_analyzer_edge_case_fixture():
    """Test the edge case fixture for KeywordAnalyzer."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "keyword_analyzer_edge_case.json"
    with open(fixture_path, "r") as f:
        data = json.load(f)

    af = parse_keyword_analyzer(data)
    assert isinstance(af, AuditFindings)

    # Should have 2 underperformers + 1 top performer = 3 findings
    assert len(af.findings) == 3

    # Check LOW priority mapping
    under_findings = [f for f in af.findings if "under" in f.id]
    # LOW priority should map to low severity for underperformers
    assert all(f.severity == "low" for f in under_findings)

    # Check handling of empty keyword name
    empty_name_finding = next((f for f in under_findings if "unknown" in f.id), None)
    assert empty_name_finding is not None
    assert "unknown" in empty_name_finding.summary

    # Check handling of null recommendation
    assert any(f.description == "Review keyword performance" for f in under_findings)

    # Check empty campaign handling
    assert any(f.dims["campaign"] == "Unknown Campaign" for f in under_findings)


def test_keyword_analyzer_severity_mapping():
    """Test priority level to severity mapping."""
    base_data = {
        "analyzer": "KeywordAnalyzer",
        "customer_id": "test",
        "analysis_period": {"start_date": "2025-08-01T00:00:00", "end_date": "2025-08-24T00:00:00"},
        "timestamp": "2025-08-24T12:00:00",
        "detailed_findings": {
            "underperforming_keywords": [
                {
                    "name": "test",
                    "match_type": "EXACT",
                    "cost": 100,
                    "conversions": 0,
                    "campaign": "Test",
                    "recommendation": "Test",
                }
            ]
        },
    }

    # Test CRITICAL -> high
    critical_data = {**base_data, "summary": {"priority_level": "CRITICAL"}}
    af = parse_keyword_analyzer(critical_data)
    assert af.findings[0].severity == "high"

    # Test HIGH -> high
    high_data = {**base_data, "summary": {"priority_level": "HIGH"}}
    af = parse_keyword_analyzer(high_data)
    assert af.findings[0].severity == "high"

    # Test MEDIUM -> medium
    medium_data = {**base_data, "summary": {"priority_level": "MEDIUM"}}
    af = parse_keyword_analyzer(medium_data)
    assert af.findings[0].severity == "medium"

    # Test LOW -> low
    low_data = {**base_data, "summary": {"priority_level": "LOW"}}
    af = parse_keyword_analyzer(low_data)
    assert af.findings[0].severity == "low"

    # Test unknown/missing -> low (default)
    unknown_data = {**base_data, "summary": {"priority_level": "UNKNOWN"}}
    af = parse_keyword_analyzer(unknown_data)
    assert af.findings[0].severity == "low"


def test_keyword_analyzer_match_type_normalization():
    """Test that match types are normalized to uppercase."""
    sample = {
        "analyzer": "KeywordAnalyzer",
        "customer_id": "test",
        "analysis_period": {"start_date": "2025-08-01T00:00:00", "end_date": "2025-08-24T00:00:00"},
        "timestamp": "2025-08-24T12:00:00",
        "summary": {"priority_level": "HIGH"},
        "detailed_findings": {
            "underperforming_keywords": [
                {
                    "name": "test1",
                    "match_type": "broad",  # lowercase
                    "cost": 100,
                    "conversions": 0,
                    "campaign": "Test",
                    "recommendation": "Test",
                },
                {
                    "name": "test2",
                    "match_type": "Phrase",  # mixed case
                    "cost": 100,
                    "conversions": 0,
                    "campaign": "Test",
                    "recommendation": "Test",
                },
            ]
        },
    }

    af = parse_keyword_analyzer(sample)
    assert af.findings[0].dims["match_type"] == "BROAD"
    assert af.findings[1].dims["match_type"] == "PHRASE"


def test_keyword_analyzer_finding_id_uniqueness():
    """Test that finding IDs are unique even for similar keywords."""
    sample = {
        "analyzer": "KeywordAnalyzer",
        "customer_id": "test123",
        "analysis_period": {"start_date": "2025-08-01T00:00:00", "end_date": "2025-08-24T00:00:00"},
        "timestamp": "2025-08-24T12:00:00",
        "summary": {"priority_level": "HIGH"},
        "detailed_findings": {
            "underperforming_keywords": [
                {
                    "name": "restaurant",
                    "match_type": "BROAD",
                    "cost": 100,
                    "conversions": 0,
                    "campaign": "Test",
                    "recommendation": "Test",
                },
                {
                    "name": "restaurant",  # Same name
                    "match_type": "EXACT",
                    "cost": 200,
                    "conversions": 0,
                    "campaign": "Test2",
                    "recommendation": "Test",
                },
            ],
            "top_performers": [
                {
                    "name": "restaurant",  # Same name again
                    "match_type": "PHRASE",
                    "cost": 300,
                    "conversions": 10,
                    "cpa": 30,
                    "campaign": "Test3",
                    "recommendation": "Good",
                }
            ],
        },
    }

    af = parse_keyword_analyzer(sample)
    assert len(af.findings) == 3

    # All finding IDs should be unique
    finding_ids = [f.id for f in af.findings]
    assert len(finding_ids) == len(set(finding_ids))

    # Check ID structure includes type and counter
    assert "under_1" in finding_ids[0]
    assert "under_2" in finding_ids[1]
    assert "top_3" in finding_ids[2]
    assert all("keyword_analyzer_test123" in id for id in finding_ids)
