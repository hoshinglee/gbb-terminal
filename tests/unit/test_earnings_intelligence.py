import hashlib
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from gbb_terminal.intelligence import (
    CompanyIdentityRepository,
    CompanyIdentityService,
    CompanyProvenance,
    CompanyRegistration,
    EarningsEvidence,
    EarningsEvent,
    EarningsIntelligenceService,
    EarningsReactionEngine,
    EarningsRepository,
    EarningsSession,
    EventTimingQuality,
    FinancialFact,
    FinancialFactRepository,
    FinancialFactService,
    NormalizedMetricsService,
)
from gbb_terminal.market_data.providers.sec import SECProvider
from gbb_terminal.storage.database import LocalMarketStore


NEW_YORK = ZoneInfo("America/New_York")


def event_at(local_time: datetime | None, announced_date: date | None = None) -> EarningsEvent:
    announcement_at = local_time.astimezone(timezone.utc) if local_time else None
    announcement_date = announced_date or local_time.date()
    session = EarningsIntelligenceService.classify_session(announcement_at)
    known_at = announcement_at or datetime.combine(announcement_date, datetime.max.time(), tzinfo=timezone.utc)
    return EarningsEvent(
        event_id=hashlib.sha256(f"{announcement_at}:{announcement_date}".encode()).hexdigest(),
        company_id="company-fixture",
        cik="0001045810",
        ticker="NVDA",
        fiscal_year=2024,
        fiscal_period="Q1",
        period_end=date(2024, 3, 31),
        announcement_at=announcement_at,
        announcement_date=announcement_date,
        session=session,
        timing_quality=EventTimingQuality.EXACT if announcement_at else EventTimingQuality.DATE_ONLY,
        evidence=EarningsEvidence(
            source="SEC EDGAR",
            dataset="sec_company_facts",
            accession_number="0001045810-24-000001",
            filing_form="10-Q",
            filing_url="https://www.sec.gov/fixture",
            filed_date=announcement_date,
            known_at=known_at,
            source_fact_ids=["fact-fixture"],
        ),
    )


def market_frame():
    dates = pd.bdate_range("2024-01-02", periods=90)
    dates = dates[dates.date != date(2024, 1, 15)]
    values = list(range(len(dates)))
    return pd.DataFrame(
        {
            "Open": [100 + value for value in values],
            "Close": [101 + value for value in values],
            "Volume": [1_000_000 + value * 10_000 for value in values],
        },
        index=dates,
    )


@pytest.mark.parametrize(
    ("local_time", "expected_session", "expected_anchor"),
    [
        (datetime(2024, 1, 12, 8, 0, tzinfo=NEW_YORK), EarningsSession.BEFORE_OPEN, date(2024, 1, 12)),
        (datetime(2024, 1, 12, 17, 0, tzinfo=NEW_YORK), EarningsSession.AFTER_CLOSE, date(2024, 1, 16)),
        (datetime(2024, 1, 13, 12, 0, tzinfo=NEW_YORK), EarningsSession.INTRADAY, date(2024, 1, 16)),
    ],
)
def test_event_session_timing_anchors_to_trading_sessions(local_time, expected_session, expected_anchor):
    event = event_at(local_time)

    reaction = EarningsReactionEngine().calculate(event, market_frame(), market_frame(), "SPY")

    assert event.session == expected_session
    assert reaction.anchor_session == expected_anchor
    assert reaction.windows["d5"].end_session > expected_anchor
    assert reaction.windows["d5"].stock_return is not None
    assert reaction.windows["d5"].benchmark_adjusted_return == 0


def test_unknown_timing_uses_next_session_and_surfaces_quality_warning():
    event = event_at(None, date(2024, 1, 13))

    reaction = EarningsReactionEngine().calculate(event, market_frame(), market_frame(), "SPY")

    assert reaction.anchor_session == date(2024, 1, 16)
    assert "Exact announcement time is unavailable" in " ".join(reaction.warnings)


def test_reaction_windows_are_session_offsets_and_volume_context_is_explicit():
    event = event_at(datetime(2024, 2, 2, 8, 0, tzinfo=NEW_YORK))
    stock = market_frame()
    benchmark = stock.copy()
    benchmark["Close"] = benchmark["Close"] * 0.9

    reaction = EarningsReactionEngine().calculate(event, stock, benchmark, "SPY")

    anchor_position = list(stock.index.date).index(reaction.anchor_session)
    assert reaction.windows["d20"].end_session == stock.index[anchor_position + 20].date()
    assert reaction.opening_gap is not None
    assert reaction.abnormal_volume is not None
    assert reaction.volume_percentile is not None
    assert reaction.path[0].relative_session == -5


def build_event_service(tmp_path):
    store = LocalMarketStore(tmp_path / "earnings.duckdb")
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
    return company, fact_repository, EarningsIntelligenceService(metrics, EarningsRepository(store.connection)), store


def event_fact(company, concept, value, unit, known_at):
    accession = "0001045810-24-000001"
    fact_id = hashlib.sha256(f"{accession}:{concept}".encode()).hexdigest()
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
        period_start=date(2024, 1, 1),
        period_end=date(2024, 3, 31),
        fiscal_year=2024,
        fiscal_period="Q1",
        form="10-Q",
        filed_date=known_at.date(),
        accepted_at=known_at,
        known_at_source="acceptance",
        accession_number=accession,
        frame="CY2024Q1",
        provenance=CompanyProvenance(
            source="SEC EDGAR",
            dataset="sec_company_facts",
            observation_timestamp=datetime(2024, 3, 31, tzinfo=timezone.utc),
            known_at=known_at,
            retrieved_at=known_at,
        ),
        source_metadata={"accessionNumber": accession},
    )


def test_event_discovery_has_stable_identity_source_evidence_and_idempotent_persistence(tmp_path):
    company, repository, service, store = build_event_service(tmp_path)
    accepted = datetime(2024, 5, 22, 20, 30, tzinfo=timezone.utc)
    repository.save_facts(
        [
            event_fact(company, "RevenueFromContractWithCustomerExcludingAssessedTax", 26_000, "USD", accepted),
            event_fact(company, "EarningsPerShareDiluted", 6.12, "USD/shares", accepted),
        ]
    )

    first = service.discover_events("NVDA", datetime(2024, 12, 31, tzinfo=timezone.utc))
    second = service.discover_events("NVDA", datetime(2024, 12, 31, tzinfo=timezone.utc))

    assert first[0].event_id == second[0].event_id
    assert first[0].session == EarningsSession.AFTER_CLOSE
    assert first[0].evidence.accession_number == "0001045810-24-000001"
    assert first[0].evidence.source_fact_ids
    assert first[0].reported_metrics["revenue"].value == 26_000
    assert store.connection.execute("SELECT count(*) FROM earnings_events").fetchone()[0] == 1
