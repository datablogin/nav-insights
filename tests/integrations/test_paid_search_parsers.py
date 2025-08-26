from nav_insights.integrations.paid_search.competitor_insights import parse_competitor_insights
from nav_insights.integrations.paid_search.keyword_analyzer import parse_keyword_analyzer
from nav_insights.integrations.paid_search.search_terms import parse_search_terms
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


def test_severity_mapping_consistency():
    """Test that all parsers use the same severity mapping."""
    # Test different priority levels across all parsers
    test_cases = [
        ("CRITICAL", "high"),
        ("high", "high"),
        ("HIGH", "high"),
        ("medium", "medium"),
        ("MEDIUM", "medium"),
        ("low", "low"),
        ("LOW", "low"),
        ("unknown", "low"),
        (None, "low"),
        ("", "low"),
    ]
    
    for priority_input, expected_severity in test_cases:
        # Test keyword analyzer
        sample = {
            "analyzer": "KeywordAnalyzer",
            "customer_id": "123",
            "analysis_period": {"start_date": "2025-07-01T00:00:00", "end_date": "2025-07-31T00:00:00"},
            "timestamp": "2025-08-24T12:00:00",
            "summary": {"priority_level": priority_input},
            "detailed_findings": {
                "underperforming_keywords": [{
                    "name": "test", "match_type": "BROAD", "cost": 10, "conversions": 0
                }]
            },
        }
        af = parse_keyword_analyzer(sample)
        assert af.findings[0].severity.value == expected_severity, f"Failed for priority {priority_input}"


def test_finding_id_uniqueness():
    """Test that finding IDs are unique even with similar entity names."""
    sample = {
        "analyzer": "KeywordAnalyzer",
        "customer_id": "123",
        "analysis_period": {"start_date": "2025-07-01T00:00:00", "end_date": "2025-07-31T00:00:00"},
        "timestamp": "2025-08-24T12:00:00",
        "summary": {"priority_level": "HIGH"},
        "detailed_findings": {
            "underperforming_keywords": [
                {"name": "test keyword", "match_type": "BROAD", "cost": 10, "conversions": 0},
                {"name": "test keyword", "match_type": "EXACT", "cost": 20, "conversions": 1},
            ],
            "top_performers": [
                {"name": "test keyword", "match_type": "PHRASE", "cost": 30, "conversions": 5},
            ]
        },
    }
    
    af = parse_keyword_analyzer(sample)
    assert len(af.findings) == 3
    
    # All IDs should be unique
    ids = [f.id for f in af.findings]
    assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"
    
    # All IDs should have hash suffixes
    for finding_id in ids:
        parts = finding_id.split("_")
        assert len(parts) >= 4, f"ID {finding_id} should have hash suffix"
        hash_part = parts[-1]
        assert len(hash_part) == 8, f"Hash part {hash_part} should be 8 characters"


def test_negative_metric_validation():
    """Test that negative metrics are rejected with proper error handling."""
    # Test negative cost in keyword analyzer
    sample = {
        "analyzer": "KeywordAnalyzer",
        "customer_id": "123",
        "analysis_period": {"start_date": "2025-07-01T00:00:00", "end_date": "2025-07-31T00:00:00"},
        "timestamp": "2025-08-24T12:00:00",
        "summary": {"priority_level": "HIGH"},
        "detailed_findings": {
            "underperforming_keywords": [
                {"name": "test", "match_type": "BROAD", "cost": -10, "conversions": 0}
            ]
        },
    }
    
    try:
        parse_keyword_analyzer(sample)
        assert False, "Should have raised NegativeMetricError"
    except Exception as e:
        assert "cost" in str(e)
        assert "-10" in str(e)
    
    # Test negative conversions in search terms
    sample = {
        "analyzer": "SearchTermsAnalyzer",
        "customer_id": "123",
        "timestamp": "2025-08-24T12:00:00",
        "summary": {"priority_level": "HIGH"},
        "detailed_findings": {
            "wasteful_search_terms": [
                {"term": "test", "cost": 10, "conversions": -5, "clicks": 10}
            ]
        },
    }
    
    try:
        parse_search_terms(sample)
        assert False, "Should have raised NegativeMetricError"
    except Exception as e:
        assert "conversions" in str(e)
        assert "-5" in str(e)
