import hashlib
from datetime import date, datetime, timezone

import pytest

from gbb_terminal.intelligence import (
    CompanyIdentityRepository,
    CompanyIdentityService,
    CompanyProvenance,
    CompanyRegistration,
    FinancialFact,
    FinancialFactRepository,
    FinancialFactService,
    MetricPeriodKind,
    NormalizedMetricsService,
)
from gbb_terminal.market_data.providers.sec import SECProvider
from gbb_terminal.storage.database import LocalMarketStore


OBSERVED = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)


def setup_metrics(tmp_path, companies):
    store = LocalMarketStore(tmp_path / "metrics.duckdb")
    sec = SECProvider()
    identity_repository = CompanyIdentityRepository(store.connection)
    identities = CompanyIdentityService(identity_repository, sec)
    registered = {}
    for cik, ticker, name in companies:
        registered[ticker] = identity_repository.upsert_company(
            CompanyRegistration(
                cik=cik,
                legal_name=name,
                primary_ticker=ticker,
                exchange="Nasdaq",
                effective_from=date(2000, 1, 1),
                provenance=CompanyProvenance(
                    source="SEC EDGAR",
                    dataset="sec_company_tickers",
                    observation_timestamp=OBSERVED,
                    known_at=OBSERVED,
                    retrieved_at=OBSERVED,
                ),
            )
        )
    fact_repository = FinancialFactRepository(store.connection)
    facts = FinancialFactService(fact_repository, identities, store, sec)
    return registered, fact_repository, NormalizedMetricsService(facts, identities)


def fact(
    company,
    concept,
    value,
    unit,
    start,
    end,
    fiscal_year,
    fiscal_period,
    accession_suffix,
    form="10-K",
):
    fact_id = hashlib.sha256(
        f"{company.company_id}:{concept}:{unit}:{start}:{end}:{accession_suffix}".encode()
    ).hexdigest()
    accession = f"{company.cik}-{accession_suffix}"
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
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        form=form,
        filed_date=end,
        accepted_at=OBSERVED,
        known_at_source="acceptance",
        accession_number=accession,
        frame=f"CY{fiscal_year}{fiscal_period}" if fiscal_period != "FY" else f"CY{fiscal_year}",
        provenance=CompanyProvenance(
            source="SEC EDGAR",
            dataset="sec_company_facts",
            observation_timestamp=datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc),
            known_at=OBSERVED,
            retrieved_at=OBSERVED,
        ),
        source_metadata={"accessionNumber": accession},
    )


def metric(result, metric_id, period_end=None):
    candidates = [item for item in result.metrics if item.metric_id == metric_id]
    if period_end:
        candidates = [item for item in candidates if item.period_end == period_end]
    return candidates[-1]


@pytest.mark.parametrize(
    ("cik", "ticker", "concept", "value", "unit", "expected"),
    [
        ("1045810", "NVDA", "RevenueFromContractWithCustomerExcludingAssessedTax", 100, "USD", 100),
        ("789019", "MSFT", "Revenues", 200, "USD", 200),
        ("1018724", "AMZN", "SalesRevenueNet", 3, "USDm", 3_000_000),
    ],
)
def test_revenue_concept_precedence_supports_three_issuer_patterns(
    tmp_path,
    cik,
    ticker,
    concept,
    value,
    unit,
    expected,
):
    companies, repository, service = setup_metrics(tmp_path, [(cik, ticker, f"{ticker} INC")])
    company = companies[ticker]
    repository.save_facts(
        [
            fact(
                company,
                concept,
                value,
                unit,
                date(2024, 1, 1),
                date(2024, 12, 31),
                2024,
                "FY",
                "24-000001",
            )
        ]
    )

    result = service.calculate(ticker, MetricPeriodKind.ANNUAL, OBSERVED)

    revenue = metric(result, "revenue")
    assert revenue.value == expected
    assert revenue.unit == "USD"
    assert len(revenue.source_fact_ids) == 1


def test_deterministic_precedence_prefers_contract_revenue_over_legacy_revenue(tmp_path):
    companies, repository, service = setup_metrics(tmp_path, [("1045810", "NVDA", "NVIDIA CORP")])
    company = companies["NVDA"]
    common = (date(2024, 1, 1), date(2024, 12, 31), 2024, "FY")
    repository.save_facts(
        [
            fact(company, "Revenues", 90, "USD", *common, "24-000001"),
            fact(
                company,
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                100,
                "USD",
                *common,
                "24-000002",
            ),
        ]
    )

    result = service.calculate("NVDA", MetricPeriodKind.ANNUAL, OBSERVED)

    revenue = metric(result, "revenue")
    assert revenue.value == 100
    assert "deterministic precedence" in revenue.warnings[0]


def test_conflicting_same_timestamp_values_surface_an_ambiguity_warning(tmp_path):
    companies, repository, service = setup_metrics(tmp_path, [("1045810", "NVDA", "NVIDIA CORP")])
    company = companies["NVDA"]
    common = (date(2024, 1, 1), date(2024, 12, 31), 2024, "FY")
    repository.save_facts(
        [
            fact(
                company,
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                100,
                "USD",
                *common,
                "24-000001",
            ),
            fact(
                company,
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                101,
                "USD",
                *common,
                "24-000002",
            ),
        ]
    )

    revenue = metric(service.calculate("NVDA", MetricPeriodKind.ANNUAL, OBSERVED), "revenue")

    assert revenue.value in {100, 101}
    assert "conflicting" in " ".join(revenue.warnings)


def test_annual_quarterly_and_ttm_metrics_are_reproducible_and_traceable(tmp_path):
    companies, repository, service = setup_metrics(tmp_path, [("1045810", "NVDA", "NVIDIA CORP")])
    company = companies["NVDA"]
    quarter_dates = [
        (date(2023, 1, 1), date(2023, 3, 31), 2023, "Q1"),
        (date(2023, 4, 1), date(2023, 6, 30), 2023, "Q2"),
        (date(2023, 7, 1), date(2023, 9, 30), 2023, "Q3"),
        (date(2023, 10, 1), date(2023, 12, 31), 2023, "Q4"),
        (date(2024, 1, 1), date(2024, 3, 31), 2024, "Q1"),
        (date(2024, 4, 1), date(2024, 6, 30), 2024, "Q2"),
        (date(2024, 7, 1), date(2024, 9, 30), 2024, "Q3"),
        (date(2024, 10, 1), date(2024, 12, 31), 2024, "Q4"),
    ]
    facts = []
    for index, (start, end, fiscal_year, fiscal_period) in enumerate(quarter_dates):
        suffix = f"{fiscal_year % 100:02d}-{index:06d}"
        revenue = 100 + index * 10
        flows = {
            "RevenueFromContractWithCustomerExcludingAssessedTax": revenue,
            "GrossProfit": revenue * 0.6,
            "OperatingIncomeLoss": revenue * 0.3,
            "NetIncomeLoss": revenue * 0.2,
            "EarningsPerShareDiluted": 1 + index * 0.1,
            "NetCashProvidedByUsedInOperatingActivities": 25,
            "PaymentsToAcquirePropertyPlantAndEquipment": 5,
            "WeightedAverageNumberOfDilutedSharesOutstanding": 100,
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": 25,
            "IncomeTaxExpenseBenefit": 5,
        }
        units = {
            "EarningsPerShareDiluted": "USD/shares",
            "WeightedAverageNumberOfDilutedSharesOutstanding": "shares",
        }
        for concept, value in flows.items():
            facts.append(
                fact(
                    company,
                    concept,
                    value,
                    units.get(concept, "USD"),
                    start,
                    end,
                    fiscal_year,
                    fiscal_period,
                    suffix,
                    form="10-Q",
                )
            )
        for concept, value in {
            "CashAndCashEquivalentsAtCarryingValue": 50,
            "LongTermDebtAndFinanceLeaseObligations": 80,
            "StockholdersEquity": 200,
        }.items():
            facts.append(
                fact(
                    company,
                    concept,
                    value,
                    "USD",
                    None,
                    end,
                    fiscal_year,
                    fiscal_period,
                    f"{suffix}-{concept}",
                    form="10-Q",
                )
            )
    repository.save_facts(facts)

    quarterly = service.calculate("NVDA", MetricPeriodKind.QUARTERLY, OBSERVED)
    ttm = service.calculate("NVDA", MetricPeriodKind.TTM, OBSERVED)

    latest_end = date(2024, 12, 31)
    assert metric(quarterly, "revenue", latest_end).value == 170
    assert metric(quarterly, "gross_margin", latest_end).value == 60
    assert metric(ttm, "revenue", latest_end).value == 620
    assert metric(ttm, "free_cash_flow", latest_end).value == 80
    assert metric(ttm, "net_debt", latest_end).value == 30
    assert metric(ttm, "return_on_equity", latest_end).value == 62
    assert metric(ttm, "revenue_growth", latest_end).value == pytest.approx(34.7826087)
    assert len(metric(ttm, "free_cash_flow", latest_end).source_fact_ids) == 8
    assert all(item.source_fact_ids for item in ttm.metrics if item.value is not None)


def test_missing_inputs_return_explicit_warnings_instead_of_fabricated_values(tmp_path):
    companies, repository, service = setup_metrics(tmp_path, [("1045810", "NVDA", "NVIDIA CORP")])
    company = companies["NVDA"]
    repository.save_facts(
        [
            fact(
                company,
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                100,
                "EUR",
                date(2024, 1, 1),
                date(2024, 12, 31),
                2024,
                "FY",
                "24-000001",
            )
        ]
    )

    result = service.calculate("NVDA", MetricPeriodKind.ANNUAL, OBSERVED)

    revenue = metric(result, "revenue")
    gross_margin = metric(result, "gross_margin")
    assert revenue.value is None
    assert "cannot be normalized" in " ".join(revenue.warnings)
    assert gross_margin.value is None
    assert "requires" in gross_margin.warnings[0]
