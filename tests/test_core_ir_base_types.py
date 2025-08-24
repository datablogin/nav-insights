"""
Tests for core IR base types (Issue #3)

Tests cover:
1. Pydantic model validation for sample fixtures (Search and Social, ≥2 fixtures each)
2. JSON Schema export availability for each model
3. DateRange validator rejecting end_date < start_date
4. Money storing as Decimal with currency code required and default currency configurable
5. Performance requirement: < 5 ms validation time per IR (avg) on laptop baseline

"""

import json
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from nav_insights.core.ir_base import (
    Money,
    AccountMeta,
    DateRange,
    Totals,
    AuditFindings,
    get_model_json_schema,
    export_all_schemas,
    DEFAULT_CURRENCY,
)
from nav_insights.domains.paid_search.ir import AuditFindingsSearch
from nav_insights.domains.paid_social.ir import AuditFindingsSocial


class TestCoreIRTypes:
    """Test core IR base types implementation"""

    def test_money_type_with_currency(self):
        """Test Money type stores amount as Decimal with currency code"""
        # Test default currency
        money = Money(amount=Decimal("1000.50"))
        assert money.currency == DEFAULT_CURRENCY
        assert isinstance(money.amount, Decimal)
        assert money.amount == Decimal("1000.50")

        # Test custom currency
        money_eur = Money(amount=Decimal("750.25"), currency="EUR")
        assert money_eur.currency == "EUR"
        assert money_eur.amount == Decimal("750.25")

    def test_money_validation(self):
        """Test Money validation guards"""
        # Test negative amount rejection
        with pytest.raises(ValueError, match="Money amount cannot be negative"):
            Money(amount=Decimal("-100"))

        # Test invalid currency code
        with pytest.raises(ValueError, match="String should match pattern"):
            Money(amount=Decimal("100"), currency="US")  # Too short

        with pytest.raises(ValueError, match="String should match pattern"):
            Money(amount=Decimal("100"), currency="USDD")  # Too long

        with pytest.raises(ValueError, match="String should match pattern"):
            Money(amount=Decimal("100"), currency="usd")  # Lowercase

    def test_date_range_validation(self):
        """Test DateRange validator rejects end_date < start_date"""
        # Valid date range
        valid_range = DateRange(start_date=date(2025, 7, 1), end_date=date(2025, 7, 31))
        assert valid_range.start_date < valid_range.end_date

        # Equal dates should be valid
        equal_range = DateRange(start_date=date(2025, 7, 1), end_date=date(2025, 7, 1))
        assert equal_range.start_date == equal_range.end_date

        # Invalid date range should raise error
        with pytest.raises(ValueError, match="end_date must be >= start_date"):
            DateRange(start_date=date(2025, 7, 31), end_date=date(2025, 7, 1))

    def test_json_schema_export(self):
        """Test JSON Schema export available for each model"""
        # Test individual model schema export
        money_schema = get_model_json_schema(Money)
        assert isinstance(money_schema, dict)
        assert "properties" in money_schema
        assert "amount" in money_schema["properties"]
        assert "currency" in money_schema["properties"]

        # Test all schemas export
        all_schemas = export_all_schemas()
        expected_models = [
            "Money",
            "EntityRef",
            "Evidence",
            "AnalyzerProvenance",
            "Finding",
            "AccountMeta",
            "DateRange",
            "Totals",
            "Aggregates",
            "AuditFindings",
        ]

        for model_name in expected_models:
            assert model_name in all_schemas
            assert isinstance(all_schemas[model_name], dict)
            assert "properties" in all_schemas[model_name]


class TestFixtureValidation:
    """Test fixture validation for Search and Social domains"""

    @pytest.fixture
    def fixtures_path(self):
        return Path(__file__).parent / "fixtures"

    def test_search_fixtures_validation(self, fixtures_path):
        """Test Search domain fixtures validate (≥2 fixtures)"""
        search_fixtures = list(fixtures_path.glob("search_fixture_*.json"))
        assert len(search_fixtures) >= 2, "Need at least 2 Search fixtures"

        for fixture_path in search_fixtures:
            with open(fixture_path) as f:
                fixture_data = json.load(f)

            # Test base AuditFindings validation
            audit_findings = AuditFindings.model_validate(fixture_data)
            assert audit_findings.schema_version == "1.0.0"
            assert isinstance(audit_findings.account, AccountMeta)
            assert isinstance(audit_findings.date_range, DateRange)
            assert isinstance(audit_findings.totals, Totals)

            # Test Search-specific validation
            search_findings = AuditFindingsSearch.model_validate(fixture_data)
            assert isinstance(search_findings, AuditFindingsSearch)

    def test_social_fixtures_validation(self, fixtures_path):
        """Test Social domain fixtures validate (≥2 fixtures)"""
        social_fixtures = list(fixtures_path.glob("social_fixture_*.json"))
        assert len(social_fixtures) >= 2, "Need at least 2 Social fixtures"

        for fixture_path in social_fixtures:
            with open(fixture_path) as f:
                fixture_data = json.load(f)

            # Test base AuditFindings validation
            audit_findings = AuditFindings.model_validate(fixture_data)
            assert audit_findings.schema_version == "1.0.0"
            assert isinstance(audit_findings.account, AccountMeta)
            assert isinstance(audit_findings.date_range, DateRange)
            assert isinstance(audit_findings.totals, Totals)

            # Test Social-specific validation
            social_findings = AuditFindingsSocial.model_validate(fixture_data)
            assert isinstance(social_findings, AuditFindingsSocial)

    def test_fixture_round_trip(self, fixtures_path):
        """Test fixtures round-trip via model_dump/model_validate"""
        all_fixtures = list(fixtures_path.glob("*_fixture_*.json"))

        for fixture_path in all_fixtures:
            with open(fixture_path) as f:
                original_data = json.load(f)

            # Load -> dump -> load cycle
            audit_findings = AuditFindings.model_validate(original_data)
            dumped_data = audit_findings.model_dump()
            reloaded_findings = AuditFindings.model_validate(dumped_data)

            # Check key fields are preserved
            assert reloaded_findings.schema_version == original_data["schema_version"]
            assert reloaded_findings.account.account_id == original_data["account"]["account_id"]
            assert len(reloaded_findings.findings) == len(original_data["findings"])


class TestPerformance:
    """Test performance requirements"""

    @pytest.fixture
    def sample_fixture_data(self):
        """Create a representative fixture for performance testing"""
        return {
            "schema_version": "1.0.0",
            "generated_at": "2025-08-24T12:00:00Z",
            "account": {"account_id": "perf-test-123", "account_name": "Performance Test Account"},
            "date_range": {"start_date": "2025-07-01", "end_date": "2025-07-31"},
            "totals": {
                "spend": {"amount": "10000.0", "currency": "USD"},
                "clicks": 50000,
                "impressions": 1000000,
                "conversions": "500.0",
                "revenue": {"amount": "25000.0", "currency": "USD"},
                "spend_usd": "10000.0",
                "revenue_usd": "25000.0",
            },
            "aggregates": {
                "match_type": {"broad_pct": 0.4},
                "quality_score": {"median": 6.5},
                "devices": {"mobile": 0.6, "desktop": 0.4},
            },
            "pmax": {},
            "conflicts": {},
            "geo": {},
            "findings": [],
            "index": {},
            "data_sources": [],
            "analyzers": [],
            "completeness": {},
        }

    def test_validation_performance(self, sample_fixture_data):
        """Test < 5 ms validation time per IR (avg) on laptop baseline"""
        iterations = 100
        validation_times = []

        for _ in range(iterations):
            start_time = time.perf_counter()
            AuditFindings.model_validate(sample_fixture_data)
            end_time = time.perf_counter()
            validation_times.append((end_time - start_time) * 1000)  # Convert to ms

        avg_time_ms = sum(validation_times) / len(validation_times)

        # Log performance for debugging
        print(f"\nValidation performance: {avg_time_ms:.3f}ms average over {iterations} iterations")
        print(f"Min: {min(validation_times):.3f}ms, Max: {max(validation_times):.3f}ms")

        # Performance requirement: < 5ms average
        assert avg_time_ms < 5.0, (
            f"Average validation time {avg_time_ms:.3f}ms exceeds 5ms requirement"
        )


class TestMoneySerializationPreservation:
    """Test Money preserves currency across serialization"""

    def test_money_serialization_preservation(self):
        """Test Money preserves currency across serialization"""
        # Create totals with different currencies
        totals = Totals(
            spend=Money(amount=Decimal("1000.50"), currency="EUR"),
            revenue=Money(amount=Decimal("3000.75"), currency="GBP"),
            spend_usd=Decimal("1100.55"),
            revenue_usd=Decimal("3750.94"),
        )

        # Serialize and deserialize
        serialized = totals.model_dump()
        deserialized = Totals.model_validate(serialized)

        # Check currency preservation
        assert deserialized.spend.currency == "EUR"
        assert deserialized.revenue.currency == "GBP"
        assert deserialized.spend.amount == Decimal("1000.50")
        assert deserialized.revenue.amount == Decimal("3000.75")

    def test_money_json_serialization(self):
        """Test Money works correctly with JSON serialization"""
        money = Money(amount=Decimal("1234.56"), currency="CAD")

        # Convert to JSON-compatible dict (mode='json' handles Decimal serialization)
        json_data = money.model_dump(mode="json")
        json_str = json.dumps(json_data)

        # Parse back from JSON
        parsed_data = json.loads(json_str)
        reconstructed_money = Money.model_validate(parsed_data)

        assert reconstructed_money.currency == "CAD"
        assert reconstructed_money.amount == Decimal("1234.56")
