import hashlib
from datetime import date, datetime, timezone

import pandas as pd
import pytest

from gbb_terminal.intelligence import (
    CompanyIdentityRepository,
    CompanyIdentityService,
    CompanyProvenance,
    CompanyRegistration,
    FinancialFact,
    FinancialFactRepository,
    FinancialFactService,
    HistoricalValuationService,
    NormalizedMetricsService,
    ValuationFrequency,
    ValuationRepository,
    ValuationStatus,
)
from gbb_terminal.market_data.providers.sec import SECProvider
from gbb_terminal.storage.database import LocalMarketStore


def build_valuation_service(tmp_path):
    store = LocalMarketStore(tmp_path / "valuation.duckdb")
    identity_repository = CompanyIdentityRepository(store.connection)
    identities = CompanyIdentityService(identity_repository, SECProvider())
    observed = datetime(2024, 2, 1, 21, tzinfo=timezone.utc)
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
    return company, fact_repository, HistoricalValuationService(metrics, ValuationRepository(store.connection)), store


def financial_fact(company, concept, value, start, end, quarter, known_at, accession, unit="USD"):
    fact_id = hashlib.sha256(f"{accession}:{concept}:{start}:{end}:{value}".encode()).hexdigest()
    return FinancialFact(
        fact_id=fact_id,
        company_id=company.company_id,
        cik=company.cik,
        taxonomy="us-gaap",
        concept=concept,
        label=concept,
        value=value,
        raw_value=str(value),
        unit=unit,
        period_start=start,
        period_end=end,
        fiscal_year=2023,
        fiscal_period=quarter,
        form="10-Q",
        filed_date=known_at.date(),
        accepted_at=known_at,
        known_at_source="acceptance",
        accession_number=accession,
        frame=f"CY2023{quarter}",
        provenance=CompanyProvenance(
            source="SEC EDGAR",
            dataset="sec_company_facts",
            observation_timestamp=datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc),
            known_at=known_at,
            retrieved_at=known_at,
        ),
        source_metadata={"accessionNumber": accession},
    )


def seed_four_quarters(company, repository, known_at, net_income=10.0, accession_prefix="original"):
    quarters = [
        (date(2023, 1, 1), date(2023, 3, 31), "Q1"),
        (date(2023, 4, 1), date(2023, 6, 30), "Q2"),
        (date(2023, 7, 1), date(2023, 9, 30), "Q3"),
        (date(2023, 10, 1), date(2023, 12, 31), "Q4"),
    ]
    facts = []
    for index, (start, end, quarter) in enumerate(quarters):
        accession = f"{company.cik}-{accession_prefix}-{index}"
        values = {
            "RevenueFromContractWithCustomerExcludingAssessedTax": (25.0, "USD", start),
            "OperatingIncomeLoss": (12.0, "USD", start),
            "NetIncomeLoss": (net_income, "USD", start),
            "NetCashProvidedByUsedInOperatingActivities": (15.0, "USD", start),
            "PaymentsToAcquirePropertyPlantAndEquipment": (5.0, "USD", start),
            "DepreciationDepletionAndAmortization": (2.0, "USD", start),
            "WeightedAverageNumberOfDilutedSharesOutstanding": (10.0, "shares", start),
            "CashAndCashEquivalentsAtCarryingValue": (20.0, "USD", None),
            "LongTermDebtAndFinanceLeaseObligations": (30.0, "USD", None),
            "StockholdersEquity": (100.0, "USD", None),
        }
        for concept, (value, unit, period_start) in values.items():
            facts.append(
                financial_fact(
                    company,
                    concept,
                    value,
                    period_start,
                    end,
                    quarter,
                    known_at,
                    accession,
                    unit,
                )
            )
    repository.save_facts(facts)


def price_frame(*dates):
    return pd.DataFrame(
        {"Close": [20.0 + index for index in range(len(dates))]},
        index=pd.to_datetime(dates),
    )


def test_historical_valuation_uses_only_fundamentals_known_by_each_market_close(tmp_path):
    company, repository, service, store = build_valuation_service(tmp_path)
    original_known_at = datetime(2024, 2, 1, 21, 1, tzinfo=timezone.utc)
    seed_four_quarters(company, repository, original_known_at)
    prices = price_frame("2024-02-01", "2024-02-02", "2024-06-28")

    before_restatement = service.calculate(
        "NVDA",
        prices,
        ValuationFrequency.DAILY,
        datetime(2024, 12, 31, tzinfo=timezone.utc),
        ["trailing_pe", "price_to_sales", "price_to_book", "ev_to_ebitda"],
    )
    seed_four_quarters(
        company,
        repository,
        datetime(2025, 3, 1, 16, tzinfo=timezone.utc),
        net_income=20,
        accession_prefix="restatement",
    )
    after_restatement = service.calculate(
        "NVDA",
        prices,
        ValuationFrequency.DAILY,
        datetime(2025, 12, 31, tzinfo=timezone.utc),
        ["trailing_pe", "price_to_sales", "price_to_book", "ev_to_ebitda"],
    )

    assert before_restatement.points["trailing_pe"][0].status == ValuationStatus.UNAVAILABLE
    assert before_restatement.points["trailing_pe"][1].value == 5.25
    assert after_restatement.points["trailing_pe"][1].value == 5.25
    assert after_restatement.points["price_to_sales"][1].value == 2.1
    assert after_restatement.points["price_to_book"][1].value == 2.1
    assert after_restatement.points["ev_to_ebitda"][1].value == pytest.approx(220 / 56)
    cached = store.connection.execute("SELECT count(*) FROM valuation_series").fetchone()[0]
    assert cached == 12


def test_non_positive_multiple_denominator_is_explicitly_not_meaningful(tmp_path):
    company, repository, service, _ = build_valuation_service(tmp_path)
    seed_four_quarters(
        company,
        repository,
        datetime(2024, 2, 1, 20, tzinfo=timezone.utc),
        net_income=-10,
    )

    result = service.calculate(
        "NVDA",
        price_frame("2024-02-02"),
        ValuationFrequency.DAILY,
        datetime(2024, 12, 31, tzinfo=timezone.utc),
        ["trailing_pe", "earnings_yield"],
    )

    assert result.points["trailing_pe"][0].status == ValuationStatus.NOT_MEANINGFUL
    assert result.points["trailing_pe"][0].value is None
    assert result.points["earnings_yield"][0].value == -20


def test_weekly_series_uses_actual_last_session_and_reports_statistics(tmp_path):
    company, repository, service, _ = build_valuation_service(tmp_path)
    seed_four_quarters(company, repository, datetime(2024, 2, 1, 20, tzinfo=timezone.utc))
    prices = price_frame("2024-02-02", "2024-02-05", "2024-02-09", "2024-02-12")

    result = service.calculate(
        "NVDA",
        prices,
        ValuationFrequency.WEEKLY,
        datetime(2024, 12, 31, tzinfo=timezone.utc),
        ["trailing_pe"],
    )

    assert [point.valuation_date.isoformat() for point in result.points["trailing_pe"]] == [
        "2024-02-02",
        "2024-02-09",
        "2024-02-12",
    ]
    assert result.statistics["trailing_pe"].sample_size == 3
    assert result.statistics["trailing_pe"].median == 5.5
