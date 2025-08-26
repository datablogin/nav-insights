import json
from decimal import Decimal
from pathlib import Path
from nav_insights.integrations.paid_search.competitor_insights import parse_competitor_insights
from nav_insights.integrations.paid_search.keyword_analyzer import parse_keyword_analyzer
from nav_insights.integrations.paid_search.search_terms import parse_search_terms
from nav_insights.integrations.paid_search.placement_audit import parse_placement_audit
from nav_insights.integrations.paid_search.video_creative import parse_video_creative
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
    assert cracker_barrel_finding.severity == "high"  # HIGH threat/cost level maps to high
    assert cracker_barrel_finding.summary == "Competitor overlap: Cracker Barrel"
    assert (
        cracker_barrel_finding.description
        == "Focus on long-tail keywords where they have low presence"
    )

    # Check entities
    assert len(cracker_barrel_finding.entities) == 1
    competitor_entity = cracker_barrel_finding.entities[0]
    assert competitor_entity.type == "other"
    assert competitor_entity.id.startswith("competitor:Cracker_Barrel_")  # Now includes hash
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
    assert family_dining_finding.severity == "high"  # HIGH competition level maps to high
    assert family_dining_finding.summary == "Gap: 'family dining near me' used by 2 competitors"
    assert family_dining_finding.description == "Add as phrase match - high opportunity"

    # Check entities - should have keyword + 2 competitors
    assert len(family_dining_finding.entities) == 3

    keyword_entity = next(e for e in family_dining_finding.entities if e.type == "keyword")
    assert keyword_entity.id.startswith("kw:family_dining_near_me_")  # Now includes hash
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
    assert comp_finding.id.startswith("COMPETITOR_McDonald_s___Co__")  # Now includes hash
    assert comp_finding.entities[0].id.startswith(
        "competitor:McDonald_s___Co__"
    )  # Now includes hash
    assert comp_finding.entities[0].name == "McDonald's & Co."  # name unchanged

    gap_finding = af.findings[1]
    assert gap_finding.id.startswith("KEYWORD_GAP_fast_food_near_me__")  # Now includes hash
    keyword_entity = next(e for e in gap_finding.entities if e.type == "keyword")
    assert keyword_entity.id.startswith("kw:fast_food_near_me__")  # Now includes hash
    assert keyword_entity.name == "fast food near me!"  # name unchanged


def test_competitor_insights_individual_severity():
    """Test that individual findings use their own threat/competition levels for severity."""
    sample = {
        "analyzer": "CompetitorInsightsAnalyzer",
        "customer_id": "severity-test",
        "analysis_period": {"start_date": "2025-07-01T00:00:00", "end_date": "2025-07-31T00:00:00"},
        "timestamp": "2025-08-24T12:00:00",
        "summary": {"priority_level": "LOW"},  # Global is low
        "detailed_findings": {
            "primary_competitors": [
                {
                    "competitor": "High Threat Competitor",
                    "competitive_threat_level": "HIGH",  # Individual high
                    "cost_competition_level": "MEDIUM",
                },
                {
                    "competitor": "Medium Threat Competitor",
                    "competitive_threat_level": "MEDIUM",  # Individual medium
                    "cost_competition_level": "LOW",
                },
                {
                    "competitor": "No Threat Data Competitor",
                    # No threat level data, should use global
                },
            ],
            "keyword_gaps": [
                {
                    "keyword": "high competition keyword",
                    "competition": "HIGH",  # Individual high
                },
                {
                    "keyword": "medium competition keyword",
                    "competition": "MEDIUM",  # Individual medium
                },
                {
                    "keyword": "no competition data keyword",
                    # No competition level, should use global
                },
            ],
        },
    }

    af = parse_competitor_insights(sample)

    # Should have 3 competitor findings + 3 keyword gap findings = 6 total
    assert len(af.findings) == 6

    # Check competitor findings use individual threat levels
    competitor_findings = [f for f in af.findings if f.id.startswith("COMPETITOR_")]

    high_threat_finding = next(f for f in competitor_findings if "High_Threat" in f.id)
    assert high_threat_finding.severity == "high"  # Uses HIGH threat level

    medium_threat_finding = next(f for f in competitor_findings if "Medium_Threat" in f.id)
    assert medium_threat_finding.severity == "medium"  # Uses MEDIUM threat level

    no_threat_finding = next(f for f in competitor_findings if "No_Threat" in f.id)
    assert no_threat_finding.severity == "low"  # Uses global LOW priority

    # Check keyword gap findings use individual competition levels
    keyword_gap_findings = [f for f in af.findings if f.id.startswith("KEYWORD_GAP_")]

    high_comp_finding = next(f for f in keyword_gap_findings if "high_competition" in f.id)
    assert high_comp_finding.severity == "high"  # Uses HIGH competition level

    medium_comp_finding = next(f for f in keyword_gap_findings if "medium_competition" in f.id)
    assert medium_comp_finding.severity == "medium"  # Uses MEDIUM competition level

    no_comp_finding = next(f for f in keyword_gap_findings if "no_competition" in f.id)
    assert no_comp_finding.severity == "low"  # Uses global LOW priority


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


def test_video_creative_smoke():
    """Basic smoke test for video_creative parser."""
    sample = {
        "analyzer": "VideoCreative",
        "customer_id": "123-456-7890",
        "analysis_period": {"start_date": "2025-08-01T00:00:00", "end_date": "2025-08-24T00:00:00"},
        "timestamp": "2025-08-24T15:30:00",
        "summary": {"priority_level": "HIGH", "total_video_spend_micros": 1000000000},
        "detailed_findings": {
            "poor_performers": [
                {
                    "creative_id": "123",
                    "creative_name": "Test Video",
                    "video_duration_seconds": 30,
                    "impressions": 1000,
                    "views": 100,
                    "view_rate": 0.10,
                    "cost_micros": 500000000,
                    "conversions": 0,
                    "cpa_micros": "N/A",
                    "campaign": "Test Campaign",
                    "ad_group": "Test Ad Group",
                    "recommendation": "Improve creative",
                    "performance_score": 0.20
                }
            ]
        },
    }
    af = parse_video_creative(sample)
    assert isinstance(af, AuditFindings)
    assert af.findings


def test_video_creative_comprehensive():
    """Test comprehensive video creative mapping with both poor and top performers."""
    sample = {
        "analyzer": "VideoCreative",
        "customer_id": "test-account-456",
        "analysis_period": {"start_date": "2025-08-01T00:00:00", "end_date": "2025-08-24T00:00:00"},
        "timestamp": "2025-08-24T15:30:00",
        "summary": {
            "total_video_creatives": 15,
            "poor_performers_count": 2,
            "top_performers_count": 1,
            "total_video_spend_micros": 2500000000,
            "average_view_rate": 0.15,
            "priority_level": "HIGH"
        },
        "detailed_findings": {
            "poor_performers": [
                {
                    "creative_id": "poor_123",
                    "creative_name": "Poor Performance Video",
                    "video_duration_seconds": 30,
                    "impressions": 10000,
                    "views": 1000,
                    "view_rate": 0.10,
                    "cost_micros": 500000000,
                    "conversions": 0,
                    "cpa_micros": "N/A",
                    "campaign": "Campaign 1",
                    "ad_group": "Ad Group 1",
                    "recommendation": "Low view rate needs improvement",
                    "performance_score": 0.15
                },
                {
                    "creative_id": "poor_456",
                    "creative_name": "Another Poor Video", 
                    "video_duration_seconds": 45,
                    "impressions": 5000,
                    "views": 400,
                    "view_rate": 0.08,
                    "cost_micros": 750000000,
                    "conversions": 1,
                    "cpa_micros": 750000000,
                    "campaign": "Campaign 2",
                    "ad_group": "Ad Group 2",
                    "recommendation": "Very low view rate",
                    "performance_score": 0.12
                }
            ],
            "top_performers": [
                {
                    "creative_id": "top_789",
                    "creative_name": "Top Performance Video",
                    "video_duration_seconds": 15,
                    "impressions": 20000,
                    "views": 8000,
                    "view_rate": 0.40,
                    "cost_micros": 400000000,
                    "conversions": 25,
                    "cpa_micros": 16000000,
                    "campaign": "Campaign 3",
                    "ad_group": "Ad Group 3",
                    "recommendation": "Excellent performance - scale up",
                    "performance_score": 0.85
                }
            ]
        },
    }

    af = parse_video_creative(sample)
    
    # Basic validation
    assert isinstance(af, AuditFindings)
    assert af.account.account_id == "test-account-456"
    assert af.date_range.start_date.isoformat() == "2025-08-01"
    assert af.date_range.end_date.isoformat() == "2025-08-24"
    
    # Should have 2 poor + 1 top = 3 total findings
    assert len(af.findings) == 3
    
    # Check totals conversion from micros
    assert af.totals.spend_usd == Decimal("2500.0")
    
    # Check video metrics in index
    assert "video_metrics" in af.index
    video_metrics = af.index["video_metrics"]
    assert video_metrics["total_video_creatives"] == Decimal("15")
    assert video_metrics["poor_performers_count"] == Decimal("2")
    assert video_metrics["top_performers_count"] == Decimal("1")
    assert video_metrics["average_view_rate"] == Decimal("0.15")
    
    # Check poor performer findings
    poor_findings = [f for f in af.findings if f.id.startswith("poor_video_")]
    assert len(poor_findings) == 2
    
    first_poor = poor_findings[0]
    assert first_poor.category == "creative"
    assert first_poor.severity == "high"  # HIGH priority maps to high
    assert first_poor.summary == "Poor video creative: Poor Performance Video"
    assert first_poor.description == "Low view rate needs improvement"
    
    # Check entities
    assert len(first_poor.entities) == 3  # creative, campaign, ad_group
    creative_entity = next(e for e in first_poor.entities if e.id.startswith("creative:"))
    assert creative_entity.id == "creative:poor_123"
    assert creative_entity.name == "Poor Performance Video"
    
    campaign_entity = next(e for e in first_poor.entities if e.type == "campaign")
    assert campaign_entity.id == "cmp:Campaign 1"
    assert campaign_entity.name == "Campaign 1"
    
    # Check metrics with micro-to-USD conversion
    assert first_poor.metrics["impressions"] == Decimal("10000")
    assert first_poor.metrics["views"] == Decimal("1000")
    assert first_poor.metrics["view_rate"] == Decimal("0.10")
    assert first_poor.metrics["cost_usd"] == Decimal("500.0")  # 500M micros = 500 USD
    assert first_poor.metrics["conversions"] == Decimal("0")
    assert "cpa_usd" not in first_poor.metrics  # N/A should be omitted
    
    # Check dimensions
    assert first_poor.dims["video_duration_seconds"] == 30
    assert first_poor.dims["campaign"] == "Campaign 1"
    assert first_poor.dims["ad_group"] == "Ad Group 1"
    assert first_poor.dims["performance_score"] == 0.15
    
    # Check second poor performer has CPA
    second_poor = poor_findings[1]
    assert "cpa_usd" in second_poor.metrics
    assert second_poor.metrics["cpa_usd"] == Decimal("750.0")  # 750M micros = 750 USD
    
    # Check top performer findings
    top_findings = [f for f in af.findings if f.id.startswith("top_video_")]
    assert len(top_findings) == 1
    
    top_finding = top_findings[0]
    assert top_finding.severity == "low"  # Top performers get low severity
    assert top_finding.summary == "Top video creative: Top Performance Video"
    assert top_finding.metrics["cpa_usd"] == Decimal("16.0")  # 16M micros = 16 USD
    assert top_finding.metrics["performance_score"] == Decimal("0.85")


def test_video_creative_happy_path_fixture():
    """Test the happy path fixture for VideoCreative."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "video_creative_happy_path.json"
    with open(fixture_path, "r") as f:
        data = json.load(f)

    af = parse_video_creative(data)
    assert isinstance(af, AuditFindings)

    # Should have 3 poor + 2 top = 5 findings
    assert len(af.findings) == 5

    # Check account mapping
    assert af.account.account_id == "123-456-7890"

    # Check date range mapping
    assert af.date_range.start_date.isoformat() == "2025-08-01"
    assert af.date_range.end_date.isoformat() == "2025-08-24"

    # Check totals conversion
    assert af.totals.spend_usd == Decimal("5420.0")  # 5420M micros

    # Check video metrics
    assert "video_metrics" in af.index
    video_metrics = af.index["video_metrics"]
    assert video_metrics["total_video_creatives"] == Decimal("25")
    assert video_metrics["average_view_rate"] == Decimal("0.18")

    # Check poor performers
    poor_findings = [f for f in af.findings if "poor_video_" in f.id]
    assert len(poor_findings) == 3
    assert all(f.severity == "high" for f in poor_findings)  # HIGH priority

    # Check first poor performer N/A CPA handling
    first_poor = poor_findings[0]
    assert first_poor.summary == "Poor video creative: Summer Sale 30s"
    assert "cpa_usd" not in first_poor.metrics  # N/A should be omitted
    assert first_poor.metrics["cost_usd"] == Decimal("892.45")

    # Check second poor performer with valid CPA
    second_poor = poor_findings[1]
    assert "cpa_usd" in second_poor.metrics
    assert second_poor.metrics["cpa_usd"] == Decimal("622.89")

    # Check top performers
    top_findings = [f for f in af.findings if "top_video_" in f.id]
    assert len(top_findings) == 2
    assert all(f.severity == "low" for f in top_findings)  # Positive findings

    first_top = top_findings[0]
    assert first_top.summary == "Top video creative: Quick Tips 15s"
    assert first_top.metrics["cpa_usd"] == Decimal("12.345")
    assert first_top.dims["video_duration_seconds"] == 15


def test_video_creative_edge_case_fixture():
    """Test the edge case fixture for VideoCreative."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "video_creative_edge_case.json"
    with open(fixture_path, "r") as f:
        data = json.load(f)

    af = parse_video_creative(data)
    assert isinstance(af, AuditFindings)

    # Should have 2 poor + 1 top = 3 findings
    assert len(af.findings) == 3

    # Check LOW priority mapping
    poor_findings = [f for f in af.findings if "poor_video_" in f.id]
    assert all(f.severity == "low" for f in poor_findings)  # LOW priority maps to low

    # Check handling of empty creative name
    empty_name_finding = next((f for f in poor_findings if "Unknown Creative" in f.summary), None)
    assert empty_name_finding is not None

    # Check handling of null values
    assert any(f.description == "Review video creative performance" for f in poor_findings)

    # Check empty campaign/ad group handling
    top_findings = [f for f in af.findings if "top_video_" in f.id]
    top_finding = top_findings[0]
    # Should only have creative entity when campaign/ad_group are empty
    assert len(top_finding.entities) == 1
    assert top_finding.entities[0].type == "other"


def test_video_creative_priority_mapping():
    """Test priority level to severity mapping."""
    base_data = {
        "analyzer": "VideoCreative",
        "customer_id": "test",
        "analysis_period": {"start_date": "2025-08-01T00:00:00", "end_date": "2025-08-24T00:00:00"},
        "timestamp": "2025-08-24T15:30:00",
        "detailed_findings": {
            "poor_performers": [
                {
                    "creative_id": "test",
                    "creative_name": "Test Creative",
                    "video_duration_seconds": 30,
                    "impressions": 1000,
                    "views": 100,
                    "view_rate": 0.10,
                    "cost_micros": 100000000,
                    "conversions": 0,
                    "campaign": "Test",
                    "ad_group": "Test",
                    "recommendation": "Test",
                    "performance_score": 0.1
                }
            ]
        },
    }

    test_cases = [
        ("CRITICAL", "high"),
        ("HIGH", "high"),
        ("MEDIUM", "medium"),
        ("LOW", "low"),
        ("UNKNOWN", "low"),
        (None, "low")
    ]

    for priority, expected_severity in test_cases:
        data = {**base_data, "summary": {"priority_level": priority}}
        af = parse_video_creative(data)
        assert af.findings[0].severity == expected_severity


def test_video_creative_micro_conversions():
    """Test micro-to-USD conversions."""
    sample = {
        "analyzer": "VideoCreative",
        "customer_id": "conversion-test",
        "analysis_period": {"start_date": "2025-08-01T00:00:00", "end_date": "2025-08-24T00:00:00"},
        "timestamp": "2025-08-24T15:30:00",
        "summary": {"total_video_spend_micros": 1500000000, "priority_level": "MEDIUM"},
        "detailed_findings": {
            "poor_performers": [
                {
                    "creative_id": "conv_test",
                    "creative_name": "Conversion Test",
                    "cost_micros": 1234567890,  # 1234.56789 USD
                    "cpa_micros": 987654321,    # 987.654321 USD
                    "impressions": 1000,
                    "views": 100,
                    "view_rate": 0.10,
                    "conversions": 1,
                    "campaign": "Test",
                    "ad_group": "Test",
                    "recommendation": "Test",
                    "performance_score": 0.1
                }
            ]
        },
    }

    af = parse_video_creative(sample)
    
    # Check totals conversion
    assert af.totals.spend_usd == Decimal("1500.0")
    
    # Check finding metrics conversion
    finding = af.findings[0]
    assert finding.metrics["cost_usd"] == Decimal("1234.567890")  # Preserves precision
    assert finding.metrics["cpa_usd"] == Decimal("987.654321")


def test_video_creative_null_cpa_handling():
    """Test that null and N/A CPA values are properly omitted."""
    sample = {
        "analyzer": "VideoCreative",
        "customer_id": "cpa-test",
        "analysis_period": {"start_date": "2025-08-01T00:00:00", "end_date": "2025-08-24T00:00:00"},
        "timestamp": "2025-08-24T15:30:00",
        "summary": {"priority_level": "HIGH"},
        "detailed_findings": {
            "poor_performers": [
                {
                    "creative_id": "null_cpa",
                    "creative_name": "Null CPA",
                    "cost_micros": 100000000,
                    "cpa_micros": None,
                    "impressions": 1000,
                    "views": 100,
                    "view_rate": 0.10,
                    "conversions": 0,
                    "campaign": "Test",
                    "ad_group": "Test",
                    "recommendation": "Test",
                    "performance_score": 0.1
                },
                {
                    "creative_id": "na_cpa",
                    "creative_name": "N/A CPA",
                    "cost_micros": 200000000,
                    "cpa_micros": "N/A",
                    "impressions": 2000,
                    "views": 200,
                    "view_rate": 0.10,
                    "conversions": 0,
                    "campaign": "Test",
                    "ad_group": "Test",
                    "recommendation": "Test",
                    "performance_score": 0.1
                }
            ]
        },
    }

    af = parse_video_creative(sample)
    assert len(af.findings) == 2
    
    # Both findings should omit CPA
    for finding in af.findings:
        assert "cpa_usd" not in finding.metrics
        assert "cost_usd" in finding.metrics  # But cost should be present
