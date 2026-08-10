import hashlib
import json
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from gbb_terminal.intelligence.estimate_models import (
    EstimateMatchStatus,
    EstimateMetric,
    EstimateObservation,
)
from gbb_terminal.intelligence.estimates import EstimateIntelligenceService
from gbb_terminal.intelligence.fact_models import FinancialFact
from gbb_terminal.intelligence.fact_repository import FinancialFactRepository
from gbb_terminal.intelligence.fact_service import FinancialFactService
from gbb_terminal.intelligence.metrics import NormalizedMetricsService
from gbb_terminal.intelligence.models import CompanyProvenance, CompanyRegistration
from gbb_terminal.intelligence.repository import CompanyIdentityRepository
from gbb_terminal.intelligence.service import CompanyIdentityService
from gbb_terminal.market_data.providers.estimates import EmptyEstimateProvider, EstimateProvider, ManualEstimateProvider
from gbb_terminal.market_data.providers.sec import SECProvider
from gbb_terminal.storage.database import LocalMarketStore


def setup_service(tmp_path, provider=None):
    store = LocalMarketStore(tmp_path / "estimates.duckdb")
    identity_repository = CompanyIdentityRepository(store.connection)
    identities = CompanyIdentityService(identity_repository, SECProvider())
    observed = datetime(2024, 1, 1, tzinfo=timezone.utc)
    company = identity_repository.upsert_company(
        CompanyRegistration(
            cik="1045810",
            legal_name="NVIDIA CORP",
            primary_ticker="NVDA",
            exchange="Nasdaq",
            effective_from=date(1999, 1, 22),
            provenance=CompanyProvenance(
                source="SEC EDGAR",
                dataset="sec_company_tickers",
                observation_timestamp=observed,
                known_at=observed,
                retrieved_at=observed,
            ),
        )
    )
    fact_repository = FinancialFactRepository(store.connection)
    facts = FinancialFactService(fact_repository, identities, store, SECProvider())
    metrics = NormalizedMetricsService(facts, identities)
    return company, fact_repository, EstimateIntelligenceService(metrics, provider or EmptyEstimateProvider())


def reported_fact(company, concept, value, unit, accepted):
    accession = "0001045810-24-000001"
    return FinancialFact(
        fact_id=hashlib.sha256(f"{accession}:{concept}".encode()).hexdigest(),
        company_id=company.company_id,
        cik=company.cik,
        taxonomy="us-gaap",
        concept=concept,
        label=concept,
        value=value,
        raw_value=str(value),
        unit=unit,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 3, 31),
        fiscal_year=2024,
        fiscal_period="Q1",
        form="10-Q",
        filed_date=accepted.date(),
        accepted_at=accepted,
        known_at_source="acceptance",
        accession_number=accession,
        frame="CY2024Q1",
        provenance=CompanyProvenance(
            source="SEC EDGAR",
            dataset="sec_company_facts",
            observation_timestamp=datetime(2024, 3, 31, tzinfo=timezone.utc),
            known_at=accepted,
            retrieved_at=accepted,
        ),
        source_metadata={"accessionNumber": accession},
    )


def estimate(estimate_id, known_at, mean=90.0, fiscal_period="Q1"):
    return EstimateObservation(
        estimate_id=estimate_id,
        provider_key="fixture_vendor",
        provider_name="Fixture Vendor",
        symbol="NVDA",
        cik="0001045810",
        metric=EstimateMetric.REVENUE,
        fiscal_year=2024,
        fiscal_period=fiscal_period,
        period_end=date(2024, 3, 31),
        unit="USD",
        mean=mean,
        median=mean - 1,
        high=mean + 5,
        low=mean - 5,
        estimate_count=12,
        observed_at=known_at,
        known_at=known_at,
    )


def test_estimate_contract_requires_known_at_timezone_and_normalized_units():
    payload = estimate("valid", datetime(2024, 5, 20, tzinfo=timezone.utc)).model_dump()
    payload["known_at"] = datetime(2024, 5, 20)

    with pytest.raises(ValidationError, match="timezone"):
        EstimateObservation.model_validate(payload)

    payload["known_at"] = datetime(2024, 5, 20, tzinfo=timezone.utc)
    payload["unit"] = "USDm"
    with pytest.raises(ValidationError, match="must use USD"):
        EstimateObservation.model_validate(payload)


def test_manual_provider_is_provider_neutral_filters_revisions_by_known_at(tmp_path):
    observations = [
        estimate("revision-1", datetime(2024, 5, 20, tzinfo=timezone.utc), 90),
        estimate("revision-2", datetime(2024, 5, 25, tzinfo=timezone.utc), 95),
    ]
    provider = ManualEstimateProvider(observations)
    company, _, service = setup_service(tmp_path, provider)

    assert isinstance(provider, EstimateProvider)
    visible = provider.estimates(company, datetime(2024, 5, 22, tzinfo=timezone.utc))
    result = service.history("NVDA", datetime(2024, 5, 22, tzinfo=timezone.utc))

    assert [observation.estimate_id for observation in visible] == ["revision-1"]
    assert [comparison.estimate.estimate_id for comparison in result.comparisons] == ["revision-1"]
    assert result.comparisons[0].match_status == EstimateMatchStatus.UNREPORTED


def test_exact_fiscal_mapping_compares_reported_result_and_preserves_lineage(tmp_path):
    provider = ManualEstimateProvider([estimate("consensus", datetime(2024, 5, 20, tzinfo=timezone.utc), 90)])
    company, repository, service = setup_service(tmp_path, provider)
    accepted = datetime(2024, 6, 1, tzinfo=timezone.utc)
    repository.save_facts(
        [
            reported_fact(company, "RevenueFromContractWithCustomerExcludingAssessedTax", 100, "USD", accepted),
            reported_fact(company, "EarningsPerShareDiluted", 2.5, "USD/shares", accepted),
        ]
    )

    result = service.history("NVDA", datetime(2024, 6, 2, tzinfo=timezone.utc), [EstimateMetric.REVENUE])
    comparison = result.comparisons[0]

    assert comparison.match_status == EstimateMatchStatus.MATCHED
    assert comparison.reported_value == 100
    assert comparison.difference == 10
    assert comparison.surprise_percent == pytest.approx(11.11111111)
    assert comparison.reported_source_fact_ids


def test_same_period_end_with_different_fiscal_label_is_not_silently_matched(tmp_path):
    provider = ManualEstimateProvider(
        [estimate("bad-period", datetime(2024, 5, 20, tzinfo=timezone.utc), fiscal_period="Q2")]
    )
    company, repository, service = setup_service(tmp_path, provider)
    accepted = datetime(2024, 6, 1, tzinfo=timezone.utc)
    repository.save_facts(
        [reported_fact(company, "RevenueFromContractWithCustomerExcludingAssessedTax", 100, "USD", accepted)]
    )

    comparison = service.history("NVDA", datetime(2024, 6, 2, tzinfo=timezone.utc)).comparisons[0]

    assert comparison.match_status == EstimateMatchStatus.PERIOD_MISMATCH
    assert comparison.reported_value is None
    assert "does not match" in comparison.warnings[0]


def test_missing_estimate_coverage_does_not_break_reported_intelligence(tmp_path):
    _, _, service = setup_service(tmp_path, EmptyEstimateProvider())

    result = service.history("NVDA", datetime(2024, 6, 2, tzinfo=timezone.utc))

    assert result.comparisons == []
    assert result.provider_key == "none"
    assert "No analyst estimate coverage" in result.warnings[0]


def test_manual_fixture_file_generates_stable_identity_without_vendor_sdk(tmp_path):
    fixture_path = tmp_path / "estimates.json"
    row = estimate("temporary", datetime(2024, 5, 20, tzinfo=timezone.utc)).model_dump(mode="json")
    row.pop("estimate_id")
    fixture_path.write_text(json.dumps({"observations": [row]}), encoding="utf-8")

    first = ManualEstimateProvider.from_path(fixture_path)
    second = ManualEstimateProvider.from_path(fixture_path)
    company, _, _ = setup_service(tmp_path / "company", first)

    assert first.estimates(company, datetime(2024, 6, 1, tzinfo=timezone.utc))[0].estimate_id == second.estimates(
        company,
        datetime(2024, 6, 1, tzinfo=timezone.utc),
    )[0].estimate_id
