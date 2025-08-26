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


def test_search_terms_comprehensive():
    """Test SearchTermsAnalyzer parser with comprehensive data validation"""
    from nav_insights.integrations.paid_search.search_terms import parse_search_terms
    from nav_insights.core.ir_base import Severity, EntityType
    from decimal import Decimal

    sample = {
        "analyzer": "SearchTermsAnalyzer",
        "customer_id": "952-408-0160",
        "analysis_period": {
            "start_date": "2025-07-25T18:07:11.481011",
            "end_date": "2025-08-24T18:07:11.481011",
        },
        "timestamp": "2025-08-24T18:07:11.481635",
        "summary": {
            "total_search_terms_analyzed": 115379,
            "wasteful_terms_identified": 2,
            "recommendations_count": 2,
            "potential_monthly_savings": 2000,
            "priority_level": "CRITICAL",
        },
        "detailed_findings": {
            "wasteful_search_terms": [
                {
                    "term": "cotton patch jobs",
                    "cost": 1834.67,
                    "conversions": 0,
                    "clicks": 234,
                    "keyword_triggered": "cotton patch",
                    "recommendation": "Add as exact negative keyword",
                },
                {
                    "term": "free food near me",
                    "cost": 934.45,
                    "conversions": 0,
                    "clicks": 167,
                    "keyword_triggered": "food near me",
                    "recommendation": "Add as broad negative keyword",
                },
            ],
            "negative_keyword_suggestions": [
                {
                    "negative_keyword": "jobs",
                    "match_type": "BROAD",
                    "estimated_savings": 2847.56,
                    "reason": "Employment-related searches",
                },
                {
                    "negative_keyword": "free",
                    "match_type": "BROAD",
                    "estimated_savings": 1834.23,
                    "reason": "Free meal searches",
                },
            ],
        },
    }

    result = parse_search_terms(sample)

    # Basic structure validation
    assert isinstance(result, AuditFindings)
    assert result.account.account_id == "952-408-0160"
    assert len(result.findings) == 4  # 2 wasteful + 2 suggestions

    # Wasteful terms validation
    wasteful_findings = [f for f in result.findings if f.id.startswith("ST_WASTE_")]
    assert len(wasteful_findings) == 2

    # Test first wasteful term
    jobs_finding = next(f for f in wasteful_findings if "jobs" in f.summary)
    assert jobs_finding.category == "keywords"
    assert jobs_finding.summary == "Wasteful search term 'cotton patch jobs' — add negative"
    assert jobs_finding.description == "Add as exact negative keyword"
    assert jobs_finding.severity == Severity.high  # CRITICAL maps to high

    # Test entities structure
    assert len(jobs_finding.entities) == 2
    search_term_entity = next(e for e in jobs_finding.entities if e.type == EntityType.search_term)
    keyword_entity = next(e for e in jobs_finding.entities if e.type == EntityType.keyword)
    assert search_term_entity.id == "st:cotton patch jobs"
    assert search_term_entity.name == "cotton patch jobs"
    assert keyword_entity.id == "kw:cotton patch"
    assert keyword_entity.name == "cotton patch"

    # Test metrics
    assert jobs_finding.metrics["cost"] == Decimal("1834.67")
    assert jobs_finding.metrics["conversions"] == Decimal("0")
    assert jobs_finding.metrics["clicks"] == Decimal("234")

    # Test dims
    assert jobs_finding.dims["keyword_triggered"] == "cotton patch"

    # Negative keyword suggestions validation
    negative_findings = [f for f in result.findings if f.id.startswith("ST_NEG_")]
    assert len(negative_findings) == 2

    # Test first negative suggestion
    jobs_neg = next(f for f in negative_findings if "jobs" in f.summary)
    assert jobs_neg.summary == "Negative keyword suggestion 'jobs'"
    assert jobs_neg.dims["match_type"] == "BROAD"
    assert jobs_neg.dims["reason"] == "Employment-related searches"
    assert jobs_neg.metrics["estimated_savings_usd"] == Decimal("2847.56")
    assert len(jobs_neg.entities) == 0  # No entities for suggestions per spec

    # Test evidence and provenance
    assert len(result.data_sources) == 1
    assert result.data_sources[0].source == "paid_search_nav.search_terms"
    assert len(result.analyzers) == 1
    assert result.analyzers[0].name == "SearchTermsAnalyzer"


def test_search_terms_missing_fields():
    """Test parser handles missing optional fields gracefully"""
    from nav_insights.integrations.paid_search.search_terms import parse_search_terms
    from decimal import Decimal

    # Minimal valid input
    sample = {
        "analyzer": "SearchTermsAnalyzer",
        "detailed_findings": {
            "wasteful_search_terms": [
                {
                    "term": "test term"
                    # Missing cost, conversions, clicks, keyword_triggered
                }
            ],
            "negative_keyword_suggestions": [
                {
                    "negative_keyword": "test"
                    # Missing match_type, estimated_savings, reason
                }
            ],
        },
    }

    result = parse_search_terms(sample)
    assert len(result.findings) == 2

    # Check wasteful term with missing fields
    wasteful = next(f for f in result.findings if f.id.startswith("ST_WASTE_"))
    assert wasteful.metrics["cost"] == Decimal("0")
    assert wasteful.metrics["conversions"] == Decimal("0")
    assert wasteful.metrics["clicks"] == Decimal("0")
    assert len(wasteful.entities) == 1  # Only search term entity, no keyword

    # Check negative suggestion with missing fields
    negative = next(f for f in result.findings if f.id.startswith("ST_NEG_"))
    assert negative.metrics["estimated_savings_usd"] == Decimal("0")
    assert negative.dims == {}  # No match_type or reason


def test_keyword_analyzer_missing_fields():
    """Test KeywordAnalyzer parser handles missing optional fields gracefully"""
    from nav_insights.integrations.paid_search.keyword_analyzer import parse_keyword_analyzer
    from decimal import Decimal

    # Minimal valid input with missing fields
    sample = {
        "analyzer": "KeywordAnalyzer",
        "customer_id": "123-456-7890",
        "analysis_period": {"start_date": "2025-07-01T00:00:00", "end_date": "2025-07-31T00:00:00"},
        "timestamp": "2025-08-24T12:00:00",
        "summary": {},  # Missing priority_level
        "detailed_findings": {
            "underperforming_keywords": [
                {
                    "name": "test keyword",
                    "cpa": "N/A",  # Test CPA handling
                    # Missing cost, conversions, match_type, campaign, recommendation
                }
            ],
            "top_performers": [
                {
                    "name": "top keyword",
                    "cpa": "N/A",  # Test CPA handling consistency
                    # Missing other fields
                }
            ],
        },
    }

    result = parse_keyword_analyzer(sample)
    assert len(result.findings) == 2

    # Check underperforming keyword
    under = next(f for f in result.findings if f.id.startswith("KW_UNDER_"))
    assert under.metrics["cost"] == Decimal("0")
    assert under.metrics["conversions"] == Decimal("0")
    assert "cpa" not in under.metrics  # CPA should not be included when "N/A"
    assert under.dims["match_type"] == ""  # Empty string for missing match_type

    # Check top performer
    top = next(f for f in result.findings if f.id.startswith("KW_TOP_"))
    assert top.metrics["cost"] == Decimal("0")
    assert top.metrics["conversions"] == Decimal("0")
    assert "cpa" not in top.metrics  # CPA handling should be consistent


def test_competitor_insights_missing_fields():
    """Test CompetitorInsights parser handles missing optional fields gracefully"""
    from nav_insights.integrations.paid_search.competitor_insights import parse_competitor_insights
    from decimal import Decimal

    # Minimal valid input
    sample = {
        "analyzer": "CompetitorInsightsAnalyzer",
        "customer_id": "123-456-7890",
        "analysis_period": {"start_date": "2025-07-01T00:00:00", "end_date": "2025-07-31T00:00:00"},
        "timestamp": "2025-08-24T12:00:00",
        "summary": {},  # Missing priority_level
        "detailed_findings": {
            "primary_competitors": [
                {
                    # Missing competitor name and all other fields
                }
            ]
        },
    }

    result = parse_competitor_insights(sample)
    assert len(result.findings) == 1

    # Check competitor with missing fields
    competitor = result.findings[0]
    assert competitor.summary == "Competitor overlap: unknown"  # Default name
    assert competitor.metrics["impression_share_overlap"] == Decimal("0")
    assert competitor.metrics["shared_keywords"] == Decimal("0")
    assert competitor.dims["cost_competition_level"] is None
    assert competitor.dims["competitive_threat_level"] is None


def test_parsers_malformed_dates():
    """Test all parsers handle malformed date strings gracefully"""
    from nav_insights.integrations.paid_search.search_terms import parse_search_terms
    from nav_insights.integrations.paid_search.keyword_analyzer import parse_keyword_analyzer
    from nav_insights.integrations.paid_search.competitor_insights import parse_competitor_insights

    # Test search_terms with malformed dates
    search_sample = {
        "analyzer": "SearchTermsAnalyzer",
        "analysis_period": {"start_date": "invalid-date", "end_date": "also-invalid"},
        "timestamp": "bad-timestamp",
        "detailed_findings": {"wasteful_search_terms": [{"term": "test"}]},
    }
    result = parse_search_terms(search_sample)
    assert isinstance(
        result.date_range.start_date, type(result.date_range.start_date)
    )  # Should not crash

    # Test keyword_analyzer with malformed dates
    keyword_sample = {
        "analyzer": "KeywordAnalyzer",
        "customer_id": "test",
        "analysis_period": {"start_date": "not-a-date"},  # Missing end_date too
        "timestamp": "invalid",
        "summary": {},
        "detailed_findings": {"underperforming_keywords": [{"name": "test"}]},
    }
    result = parse_keyword_analyzer(keyword_sample)
    assert isinstance(
        result.date_range.start_date, type(result.date_range.start_date)
    )  # Should not crash

    # Test competitor_insights with malformed dates
    competitor_sample = {
        "analyzer": "CompetitorInsightsAnalyzer",
        "customer_id": "test",
        "analysis_period": {},  # Empty analysis_period
        "timestamp": "",  # Empty timestamp
        "summary": {},
        "detailed_findings": {"primary_competitors": []},
    }
    result = parse_competitor_insights(competitor_sample)
    assert isinstance(
        result.date_range.start_date, type(result.date_range.start_date)
    )  # Should not crash
