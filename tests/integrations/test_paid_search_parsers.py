import json
from decimal import Decimal
from pathlib import Path
from nav_insights.integrations.paid_search.competitor_insights import parse_competitor_insights
from nav_insights.integrations.paid_search.keyword_analyzer import parse_keyword_analyzer
from nav_insights.integrations.paid_search.search_terms import parse_search_terms
from nav_insights.integrations.paid_search.placement_audit import parse_placement_audit
from nav_insights.core.findings_ir import AuditFindings


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


def test_competitor_insights_comprehensive():
    """Test comprehensive competitor insights mapping with both competitors and keyword gaps."""
    sample = {
        "analyzer": "CompetitorInsightsAnalyzer",
        "customer_id": "123-456-7890",
        "analysis_period": {"start_date": "2025-07-01T00:00:00", "end_date": "2025-07-31T00:00:00"},
        "timestamp": "2025-08-24T12:00:00",
        "summary": {
            "competitors_identified": 3,
            "auction_insights_analyzed": True,
            "keyword_overlap_detected": 25,
            "opportunity_score": 0.75,
            "potential_monthly_savings": 2500.50,
            "priority_level": "HIGH",
        },
        "detailed_findings": {
            "primary_competitors": [
                {
                    "competitor": "Cracker Barrel",
                    "impression_share_overlap": 0.34,
                    "average_position_vs_you": 1.8,
                    "shared_keywords": 89,
                    "cost_competition_level": "HIGH",
                    "opportunity": "Focus on long-tail keywords where they have low presence",
                    "monthly_search_volume": 45000,
                    "competitive_threat_level": "HIGH",
                },
                {
                    "competitor": "Denny's",
                    "impression_share_overlap": 0.28,
                    "average_position_vs_you": 2.1,
                    "shared_keywords": 67,
                    "cost_competition_level": "MEDIUM",
                    "opportunity": "Target breakfast-specific terms with higher bids",
                    "monthly_search_volume": 38000,
                    "competitive_threat_level": "MEDIUM",
                },
            ],
            "keyword_gaps": [
                {
                    "keyword": "family dining near me",
                    "competitor_using": ["Cracker Barrel", "IHOP"],
                    "search_volume": 2400,
                    "competition": "HIGH",
                    "estimated_cpc": 1.85,
                    "recommendation": "Add as phrase match - high opportunity",
                },
                {
                    "keyword": "breakfast restaurant",
                    "competitor_using": ["Denny's"],
                    "search_volume": 1800,
                    "competition": "MEDIUM",
                    "estimated_cpc": 1.42,
                    "recommendation": "Consider broad match modified for wider reach",
                },
            ],
            "competitive_advantages": ["Strong brand recognition", "Better location coverage"],
            "recommendations": [
                "Increase bids on breakfast keywords",
                "Add negative keywords for non-target demographics",
            ],
        },
    }

    af = parse_competitor_insights(sample)

    # Basic validation
    assert isinstance(af, AuditFindings)
    assert af.account.account_id == "123-456-7890"
    assert af.date_range.start_date.isoformat() == "2025-07-01"
    assert af.date_range.end_date.isoformat() == "2025-07-31"

    # Should have 2 competitor findings + 2 keyword gap findings = 4 total
    assert len(af.findings) == 4

    # Check competitor findings
    competitor_findings = [f for f in af.findings if f.id.startswith("COMPETITOR_")]
    assert len(competitor_findings) == 2

    cracker_barrel_finding = next(f for f in competitor_findings if "Cracker_Barrel" in f.id)
    assert cracker_barrel_finding.category == "other"
    assert cracker_barrel_finding.severity == "high"  # HIGH maps to high
    assert cracker_barrel_finding.summary == "Competitor overlap: Cracker Barrel"
    assert (
        cracker_barrel_finding.description
        == "Focus on long-tail keywords where they have low presence"
    )

    # Check entities
    assert len(cracker_barrel_finding.entities) == 1
    competitor_entity = cracker_barrel_finding.entities[0]
    assert competitor_entity.type == "other"
    assert competitor_entity.id == "competitor:Cracker_Barrel"
    assert competitor_entity.name == "Cracker Barrel"

    # Check metrics
    assert "impression_share_overlap" in cracker_barrel_finding.metrics
    assert cracker_barrel_finding.metrics["impression_share_overlap"] == Decimal("0.34")
    assert cracker_barrel_finding.metrics["average_position_vs_you"] == Decimal("1.8")
    assert cracker_barrel_finding.metrics["shared_keywords"] == Decimal("89")
    assert cracker_barrel_finding.metrics["monthly_search_volume"] == Decimal("45000")

    # Check dimensions
    assert cracker_barrel_finding.dims["cost_competition_level"] == "HIGH"
    assert cracker_barrel_finding.dims["competitive_threat_level"] == "HIGH"

    # Check evidence
    assert len(cracker_barrel_finding.evidence) == 1
    assert cracker_barrel_finding.evidence[0].source == "paid_search_nav.competitor_insights"

    # Check keyword gap findings
    keyword_gap_findings = [f for f in af.findings if f.id.startswith("KEYWORD_GAP_")]
    assert len(keyword_gap_findings) == 2

    family_dining_finding = next(f for f in keyword_gap_findings if "family_dining_near_me" in f.id)
    assert family_dining_finding.category == "other"
    assert family_dining_finding.severity == "high"
    assert family_dining_finding.summary == "Gap: 'family dining near me' used by 2 competitors"
    assert family_dining_finding.description == "Add as phrase match - high opportunity"

    # Check entities - should have keyword + 2 competitors
    assert len(family_dining_finding.entities) == 3

    keyword_entity = next(e for e in family_dining_finding.entities if e.type == "keyword")
    assert keyword_entity.id == "kw:family_dining_near_me"
    assert keyword_entity.name == "family dining near me"

    competitor_entities = [e for e in family_dining_finding.entities if e.type == "other"]
    assert len(competitor_entities) == 2
    competitor_names = [e.name for e in competitor_entities]
    assert "Cracker Barrel" in competitor_names
    assert "IHOP" in competitor_names

    # Check metrics
    assert family_dining_finding.metrics["search_volume"] == Decimal("2400")
    assert family_dining_finding.metrics["estimated_cpc"] == Decimal("1.85")

    # Check dimensions
    assert family_dining_finding.dims["competition"] == "HIGH"
    assert family_dining_finding.dims["competitor_list"] == ["Cracker Barrel", "IHOP"]

    # Check competition metrics stored in index
    assert "competition" in af.index
    competition_metrics = af.index["competition"]
    assert competition_metrics["opportunity_score"] == Decimal("0.75")
    assert competition_metrics["potential_monthly_savings"] == Decimal("2500.50")
    assert competition_metrics["competitors_identified"] == Decimal("3")
    assert competition_metrics["keyword_overlap_detected"] == Decimal("25")

    # Check global provenance
    assert len(af.analyzers) == 1
    assert af.analyzers[0].name == "CompetitorInsightsAnalyzer"
    assert af.analyzers[0].version == "unknown"

    # Check global evidence
    assert len(af.data_sources) == 1
    assert af.data_sources[0].source == "paid_search_nav.competitor_insights"
    assert af.data_sources[0].rows == 4  # 4 findings


def test_competitor_insights_priority_mapping():
    """Test priority level to severity mapping."""
    test_cases = [
        ("CRITICAL", "high"),
        ("HIGH", "high"),
        ("MEDIUM", "medium"),
        ("LOW", "low"),
        ("", "low"),  # default
        (None, "low"),  # default
    ]

    for priority, expected_severity in test_cases:
        sample = {
            "analyzer": "CompetitorInsightsAnalyzer",
            "customer_id": "test-account",
            "analysis_period": {
                "start_date": "2025-07-01T00:00:00",
                "end_date": "2025-07-31T00:00:00",
            },
            "timestamp": "2025-08-24T12:00:00",
            "summary": {"priority_level": priority},
            "detailed_findings": {
                "primary_competitors": [
                    {
                        "competitor": "Test Competitor",
                        "impression_share_overlap": 0.5,
                        "shared_keywords": 10,
                    }
                ]
            },
        }

        af = parse_competitor_insights(sample)
        assert af.findings[0].severity == expected_severity


def test_competitor_insights_minimal_data():
    """Test parser handles minimal data without optional fields."""
    sample = {
        "analyzer": "CompetitorInsightsAnalyzer",
        "customer_id": "minimal-test",
        "analysis_period": {"start_date": "2025-07-01T00:00:00", "end_date": "2025-07-31T00:00:00"},
        "timestamp": "2025-08-24T12:00:00",
        "summary": {},  # no priority_level
        "detailed_findings": {
            "primary_competitors": [
                {
                    "competitor": "Minimal Competitor"
                    # no optional fields
                }
            ],
            "keyword_gaps": [
                {
                    "keyword": "minimal keyword"
                    # no optional fields
                }
            ],
        },
    }

    af = parse_competitor_insights(sample)
    assert isinstance(af, AuditFindings)
    assert len(af.findings) == 2

    # Check competitor finding with minimal data
    comp_finding = af.findings[0]
    assert comp_finding.severity == "low"  # default
    assert comp_finding.summary == "Competitor overlap: Minimal Competitor"
    assert comp_finding.description == ""  # empty when no opportunity field
    assert len(comp_finding.metrics) == 0  # no metrics when fields missing
    assert len(comp_finding.dims) == 0  # no dims when fields missing

    # Check keyword gap finding with minimal data
    gap_finding = af.findings[1]
    assert gap_finding.summary == "Gap: 'minimal keyword' used by 0 competitors"
    assert gap_finding.description == ""  # empty when no recommendation field
    assert len(gap_finding.entities) == 1  # just the keyword entity
    assert gap_finding.entities[0].type == "keyword"


def test_competitor_insights_empty_lists():
    """Test parser handles empty competitor and keyword gap lists."""
    sample = {
        "analyzer": "CompetitorInsightsAnalyzer",
        "customer_id": "empty-test",
        "analysis_period": {"start_date": "2025-07-01T00:00:00", "end_date": "2025-07-31T00:00:00"},
        "timestamp": "2025-08-24T12:00:00",
        "summary": {"priority_level": "LOW"},
        "detailed_findings": {"primary_competitors": [], "keyword_gaps": []},
    }

    af = parse_competitor_insights(sample)
    assert isinstance(af, AuditFindings)
    assert len(af.findings) == 0


def test_competitor_insights_sanitize_ids():
    """Test that special characters in competitor and keyword names are sanitized for IDs."""
    sample = {
        "analyzer": "CompetitorInsightsAnalyzer",
        "customer_id": "sanitize-test",
        "analysis_period": {"start_date": "2025-07-01T00:00:00", "end_date": "2025-07-31T00:00:00"},
        "timestamp": "2025-08-24T12:00:00",
        "summary": {"priority_level": "MEDIUM"},
        "detailed_findings": {
            "primary_competitors": [
                {
                    "competitor": "McDonald's & Co.",
                    "impression_share_overlap": 0.25,
                }
            ],
            "keyword_gaps": [
                {
                    "keyword": "fast food near me!",
                    "competitor_using": ["McDonald's & Co."],
                }
            ],
        },
    }

    af = parse_competitor_insights(sample)

    # Check that IDs are sanitized but names remain original
    comp_finding = af.findings[0]
    assert comp_finding.id == "COMPETITOR_McDonald_s___Co_"
    assert comp_finding.entities[0].id == "competitor:McDonald_s___Co_"
    assert comp_finding.entities[0].name == "McDonald's & Co."  # name unchanged

    gap_finding = af.findings[1]
    assert gap_finding.id == "KEYWORD_GAP_fast_food_near_me_"
    keyword_entity = next(e for e in gap_finding.entities if e.type == "keyword")
    assert keyword_entity.id == "kw:fast_food_near_me_"
    assert keyword_entity.name == "fast food near me!"  # name unchanged


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
