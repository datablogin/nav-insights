"""Unit tests for negative_conflicts analyzer → IR mapping.

Tests validation of fixtures and key field semantics for Issue #39.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from nav_insights.core.ir_base import AuditFindings, FindingCategory, Severity


class TestNegativeConflictsMapping:
    """Test negative_conflicts analyzer IR mapping and fixtures."""

    def test_happy_path_fixture_validation(self):
        """Test that happy path fixture validates against IR schema."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_happy_path.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        # Should validate without errors
        ir = AuditFindings.model_validate(fixture_data)

        # Basic structure validation
        assert ir.schema_version == "1.0.0"
        assert ir.account.account_id == "456-789-0123"
        assert ir.account.account_name == "SportStore Plus"

        # Date range validation
        assert ir.date_range.start_date.year == 2025
        assert ir.date_range.start_date.month == 8
        assert ir.date_range.start_date.day == 1
        assert ir.date_range.end_date.day == 31

    def test_edge_case_fixture_validation(self):
        """Test that edge case fixture validates against IR schema."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_edge_case.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        # Should validate without errors
        ir = AuditFindings.model_validate(fixture_data)

        # Basic structure validation
        assert ir.schema_version == "1.0.0"
        assert ir.account.account_id == "000-000-0001"
        assert ir.account.account_name == "Small Test Account"

        # Edge case specific validations
        assert len(ir.findings) == 2
        assert all(f.severity == Severity.low for f in ir.findings)
        assert ir.completeness.get("low_volume_account") is True

    def test_findings_structure_happy_path(self):
        """Test that findings have correct structure and categories."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_happy_path.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        ir = AuditFindings.model_validate(fixture_data)

        # Should have 3 findings
        assert len(ir.findings) == 3

        # All findings should be conflicts category
        for finding in ir.findings:
            assert finding.category == FindingCategory.conflicts

        # Check specific finding types
        blocking_findings = [
            f for f in ir.findings if "blocking" in f.dims.get("conflict_type", "")
        ]
        broad_findings = [
            f for f in ir.findings if "overly_broad" in f.dims.get("conflict_type", "")
        ]

        assert len(blocking_findings) == 2
        assert len(broad_findings) == 1

    def test_metrics_data_types(self):
        """Test that metrics use correct data types (Decimal for financial values)."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_happy_path.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        ir = AuditFindings.model_validate(fixture_data)

        # Check totals use proper Money type
        assert isinstance(ir.totals.spend.amount, Decimal)
        assert isinstance(ir.totals.revenue.amount, Decimal)
        assert ir.totals.spend.currency == "USD"
        assert ir.totals.revenue.currency == "USD"

        # Check finding metrics are Decimal
        for finding in ir.findings:
            for metric_name, metric_value in finding.metrics.items():
                assert isinstance(metric_value, Decimal), (
                    f"Metric {metric_name} should be Decimal, got {type(metric_value)}"
                )

    def test_conflicts_namespace_metrics(self):
        """Test that conflicts namespace contains expected metrics."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_happy_path.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        ir = AuditFindings.model_validate(fixture_data)

        # Check conflicts namespace
        assert "negatives_blocking_converters_count" in ir.conflicts
        assert "blocked_conversions_total" in ir.conflicts
        assert "revenue_impact_usd" in ir.conflicts
        assert "overly_broad_negatives_count" in ir.conflicts

        # Verify values match expected types
        assert isinstance(ir.conflicts["negatives_blocking_converters_count"], Decimal)
        assert isinstance(ir.conflicts["blocked_conversions_total"], Decimal)
        assert isinstance(ir.conflicts["revenue_impact_usd"], Decimal)
        assert isinstance(ir.conflicts["overly_broad_negatives_count"], Decimal)

    def test_entity_structure(self):
        """Test that entities have correct structure and types."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_happy_path.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        ir = AuditFindings.model_validate(fixture_data)

        # Check first finding entities
        finding = ir.findings[0]
        entity_types = {entity.type for entity in finding.entities}

        # Should have keyword, search_term, campaign, ad_group entities
        expected_types = {"keyword", "search_term", "campaign", "ad_group"}
        assert expected_types.issubset(entity_types)

        # Check entity IDs follow expected patterns
        keyword_entities = [e for e in finding.entities if e.type == "keyword"]
        search_term_entities = [e for e in finding.entities if e.type == "search_term"]

        assert len(keyword_entities) == 1
        assert len(search_term_entities) == 1

        # Check ID patterns
        assert keyword_entities[0].id.startswith("neg:")
        assert search_term_entities[0].id.startswith("st:")

    def test_evidence_structure(self):
        """Test that evidence has correct structure and source attribution."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_happy_path.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        ir = AuditFindings.model_validate(fixture_data)

        # Check evidence on findings
        for finding in ir.findings:
            assert len(finding.evidence) >= 1
            evidence = finding.evidence[0]

            assert evidence.source == "paid_search_nav.negative_conflicts"
            assert evidence.rows is not None
            assert evidence.rows >= 1

    def test_totals_alignment(self):
        """Test that totals align with individual finding metrics."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_happy_path.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        ir = AuditFindings.model_validate(fixture_data)

        # Calculate total revenue impact from findings
        total_revenue_impact = Decimal("0")
        total_blocked_conversions = Decimal("0")

        for finding in ir.findings:
            if "revenue_lost_usd" in finding.metrics:
                total_revenue_impact += finding.metrics["revenue_lost_usd"]
            elif "total_revenue_impact_usd" in finding.metrics:
                total_revenue_impact += finding.metrics["total_revenue_impact_usd"]

            if "conversions_lost" in finding.metrics:
                total_blocked_conversions += finding.metrics["conversions_lost"]

        # Should align with conflicts namespace (allowing for small rounding differences)
        conflicts_revenue = ir.conflicts["revenue_impact_usd"]
        conflicts_conversions = ir.conflicts["blocked_conversions_total"]

        assert abs(total_revenue_impact - conflicts_revenue) <= Decimal("0.01")
        assert abs(total_blocked_conversions - conflicts_conversions) <= Decimal("0.01")

    def test_provenance_information(self):
        """Test that provenance information is properly captured."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_happy_path.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        ir = AuditFindings.model_validate(fixture_data)

        # Check analyzer provenance
        assert len(ir.analyzers) >= 1
        analyzer = ir.analyzers[0]

        assert analyzer.name == "negative_conflicts"
        assert analyzer.version == "1.0.0"
        assert analyzer.git_sha is not None
        assert analyzer.started_at is not None
        assert analyzer.finished_at is not None

    def test_edge_case_minimal_data(self):
        """Test edge case handling with minimal data."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_edge_case.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        ir = AuditFindings.model_validate(fixture_data)

        # Should handle minimal data gracefully
        assert len(ir.findings) == 2
        assert all(f.severity == Severity.low for f in ir.findings)

        # Low confidence for minimal data
        assert all(f.confidence < 0.5 for f in ir.findings)

        # Find the broad finding (overly broad type)
        broad_finding = next(
            f for f in ir.findings if f.dims.get("conflict_type") == "overly_broad"
        )
        assert broad_finding.metrics["total_revenue_impact_usd"] == Decimal("5.0")

        # Completeness flags should indicate data limitations
        assert ir.completeness.get("has_conversion_data") is False
        assert ir.completeness.get("insufficient_data_warning") is True

    def test_fixture_serialization_roundtrip(self):
        """Test that fixtures can be serialized and deserialized without data loss."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_happy_path.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            original_data = json.load(f)

        # Load through Pydantic
        ir = AuditFindings.model_validate(original_data)

        # Serialize back to dict
        serialized_data = ir.model_dump()

        # Re-validate
        ir_roundtrip = AuditFindings.model_validate(serialized_data)

        # Key fields should match
        assert ir.account.account_id == ir_roundtrip.account.account_id
        assert len(ir.findings) == len(ir_roundtrip.findings)
        assert ir.conflicts["revenue_impact_usd"] == ir_roundtrip.conflicts["revenue_impact_usd"]

    def test_invalid_date_range_validation(self):
        """Test validation fails for malformed dates and invalid date ranges."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_happy_path.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        # Test invalid date format
        invalid_data = fixture_data.copy()
        invalid_data["date_range"]["start_date"] = "invalid-date"

        with pytest.raises(Exception):  # Pydantic validation error
            AuditFindings.model_validate(invalid_data)

        # Test end_date before start_date
        invalid_data = fixture_data.copy()
        invalid_data["date_range"]["start_date"] = "2025-08-31"
        invalid_data["date_range"]["end_date"] = "2025-08-01"

        with pytest.raises(Exception):  # Validation error
            AuditFindings.model_validate(invalid_data)

    def test_negative_revenue_validation(self):
        """Test validation handles negative revenue values appropriately."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_happy_path.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        # Test negative total revenue (should fail validation due to Money constraints)
        fixture_data["totals"]["revenue"]["amount"] = "-1000.0"

        # Should fail validation - Money type doesn't allow negative amounts
        with pytest.raises(Exception):  # ValidationError for negative Money
            AuditFindings.model_validate(fixture_data)

    def test_missing_required_fields(self):
        """Test validation fails when required fields are missing."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_happy_path.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        # Test missing account_id (required field)
        invalid_data = fixture_data.copy()
        del invalid_data["account"]["account_id"]

        with pytest.raises(Exception):
            AuditFindings.model_validate(invalid_data)

        # Test missing date_range (required field)
        invalid_data = fixture_data.copy()
        del invalid_data["date_range"]

        with pytest.raises(Exception):
            AuditFindings.model_validate(invalid_data)

    def test_boundary_values(self):
        """Test boundary values (zero, extremely large numbers)."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_happy_path.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        # Test zero values
        zero_data = fixture_data.copy()
        zero_data["totals"]["spend"]["amount"] = "0.0"
        zero_data["totals"]["revenue"]["amount"] = "0.0"
        zero_data["totals"]["conversions"] = "0.0"
        zero_data["conflicts"]["revenue_impact_usd"] = "0.0"

        ir = AuditFindings.model_validate(zero_data)
        assert ir.totals.spend.amount == Decimal("0.0")
        assert ir.totals.revenue.amount == Decimal("0.0")
        assert ir.conflicts["revenue_impact_usd"] == Decimal("0.0")

        # Test extremely large numbers (but within reasonable business bounds)
        large_data = fixture_data.copy()
        large_data["totals"]["spend"]["amount"] = "999999999.99"
        large_data["totals"]["revenue"]["amount"] = "999999999.99"
        large_data["conflicts"]["revenue_impact_usd"] = "999999999.99"

        ir = AuditFindings.model_validate(large_data)
        assert ir.totals.spend.amount == Decimal("999999999.99")
        assert ir.totals.revenue.amount == Decimal("999999999.99")
        assert ir.conflicts["revenue_impact_usd"] == Decimal("999999999.99")

    def test_confidence_score_boundaries(self):
        """Test confidence score boundaries (0.0 to 1.0)."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "negative_conflicts_fixture_happy_path.json"
        )

        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        # Test minimum confidence (0.0)
        fixture_data["findings"][0]["confidence"] = 0.0
        ir = AuditFindings.model_validate(fixture_data)
        assert ir.findings[0].confidence == 0.0

        # Test maximum confidence (1.0)
        fixture_data["findings"][0]["confidence"] = 1.0
        ir = AuditFindings.model_validate(fixture_data)
        assert ir.findings[0].confidence == 1.0

        # Test invalid confidence (should fail)
        fixture_data["findings"][0]["confidence"] = 1.5
        with pytest.raises(Exception):  # Should fail validation
            AuditFindings.model_validate(fixture_data)
