from datetime import date, datetime, timezone

from gbb_terminal.intelligence import (
    CompanyIdentityRepository,
    CompanyIdentityService,
    CompanyProvenance,
    CompanyRegistration,
    FinancialFactQuery,
    FinancialFactRepository,
    FinancialFactService,
)
from gbb_terminal.market_data.models import DataEnvelope
from gbb_terminal.market_data.providers.sec import SECProvider
from gbb_terminal.market_data.providers.base import ProviderUnavailable
from gbb_terminal.storage.database import LocalMarketStore


def setup_services(tmp_path):
    store = LocalMarketStore(tmp_path / "facts.duckdb")
    sec = SECProvider()
    identities = CompanyIdentityService(CompanyIdentityRepository(store.connection), sec)
    observed = datetime(2024, 1, 2, 12, tzinfo=timezone.utc)
    company = identities.repository.upsert_company(
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
    repository = FinancialFactRepository(store.connection)
    return store, company, FinancialFactService(repository, identities, store, sec)


def company_facts_envelope(retrieved_at: datetime) -> DataEnvelope[dict]:
    return DataEnvelope(
        dataset="sec_company_facts",
        symbol="0001045810",
        data={
            "cik": 1045810,
            "entityName": "NVIDIA CORP",
            "facts": {
                "us-gaap": {
                    "RevenueFromContractWithCustomerExcludingAssessedTax": {
                        "label": "Revenue",
                        "description": "Revenue from customers.",
                        "units": {
                            "USD": [
                                {
                                    "start": "2023-01-01",
                                    "end": "2023-12-31",
                                    "val": 100,
                                    "accn": "0001045810-24-000001",
                                    "fy": 2023,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2024-02-20",
                                    "frame": "CY2023",
                                },
                                {
                                    "start": "2023-01-01",
                                    "end": "2023-12-31",
                                    "val": 110,
                                    "accn": "0001045810-25-000002",
                                    "fy": 2023,
                                    "fp": "FY",
                                    "form": "10-K/A",
                                    "filed": "2025-03-01",
                                    "frame": "CY2023",
                                },
                            ]
                        },
                    },
                    "NetIncomeLoss": {
                        "label": "Net Income",
                        "description": "Quarterly net income.",
                        "units": {
                            "USD": [
                                {
                                    "start": "2024-01-01",
                                    "end": "2024-03-31",
                                    "val": 20,
                                    "accn": "0001045810-24-000003",
                                    "fy": 2024,
                                    "fp": "Q1",
                                    "form": "10-Q",
                                    "filed": "2024-05-10",
                                    "frame": "CY2024Q1",
                                }
                            ]
                        },
                    },
                }
            },
        },
        observation_timestamp=retrieved_at,
        known_at=retrieved_at,
        retrieved_at=retrieved_at,
        status="Delayed Public Data",
        source="SEC EDGAR",
        quality_warnings=["Company facts can be amended."],
    )


def submissions_envelope(retrieved_at: datetime) -> DataEnvelope[dict]:
    accessions = [
        "0001045810-24-000001",
        "0001045810-25-000002",
        "0001045810-24-000003",
    ]
    accepted = [
        "2024-02-20T21:15:00Z",
        "2025-03-01T16:30:00Z",
        "2024-05-10T12:00:00Z",
    ]
    return DataEnvelope(
        dataset="sec_submissions",
        symbol="0001045810",
        data={"filings": {"recent": {"accessionNumber": accessions, "acceptanceDateTime": accepted}}},
        observation_timestamp=retrieved_at,
        known_at=retrieved_at,
        retrieved_at=retrieved_at,
        status="Delayed Public Data",
        source="SEC EDGAR",
    )


def test_full_history_is_append_safe_and_restated_periods_are_retained(tmp_path):
    _, company, service = setup_services(tmp_path)
    retrieved = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)

    first = service.ingest_company_facts(
        company,
        company_facts_envelope(retrieved),
        submissions_envelope(retrieved),
    )
    repeated = service.ingest_company_facts(
        company,
        company_facts_envelope(retrieved),
        submissions_envelope(retrieved),
    )

    history = service.history("NVDA")
    revenue = [fact for fact in history if fact.concept == "RevenueFromContractWithCustomerExcludingAssessedTax"]
    assert first.observations_seen == 3
    assert first.observations_inserted == 3
    assert repeated.observations_inserted == 0
    assert len(history) == 3
    assert len(revenue) == 2
    assert {fact.value for fact in revenue} == {100, 110}
    assert {fact.accession_number for fact in revenue} == {
        "0001045810-24-000001",
        "0001045810-25-000002",
    }


def test_as_of_boundary_excludes_later_restatement(tmp_path):
    _, company, service = setup_services(tmp_path)
    retrieved = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
    service.ingest_company_facts(company, company_facts_envelope(retrieved), submissions_envelope(retrieved))

    historical = service.history(
        "0001045810",
        FinancialFactQuery(
            concepts=["RevenueFromContractWithCustomerExcludingAssessedTax"],
            as_of=datetime(2024, 12, 31, 23, 59, tzinfo=timezone.utc),
        ),
    )

    assert len(historical) == 1
    assert historical[0].value == 100
    assert historical[0].known_at_source == "acceptance"
    assert historical[0].source_metadata["accessionNumber"] == "0001045810-24-000001"


def test_missing_acceptance_time_uses_visible_conservative_fallback(tmp_path):
    _, company, service = setup_services(tmp_path)
    retrieved = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
    service.ingest_company_facts(company, company_facts_envelope(retrieved))

    fact = service.history(
        "NVDA",
        FinancialFactQuery(concepts=["NetIncomeLoss"]),
    )[0]

    assert fact.known_at_source == "filed_date_fallback"
    assert fact.provenance.known_at.date() == date(2024, 5, 10)
    assert "conservatively" in fact.provenance.quality_warnings[-1]


def test_later_acceptance_metadata_enriches_the_same_source_fact(tmp_path):
    _, company, service = setup_services(tmp_path)
    retrieved = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
    service.ingest_company_facts(company, company_facts_envelope(retrieved))
    enriched = service.ingest_company_facts(
        company,
        company_facts_envelope(retrieved),
        submissions_envelope(retrieved),
    )

    facts = service.history(
        "NVDA",
        FinancialFactQuery(concepts=["NetIncomeLoss"]),
    )

    assert enriched.observations_inserted == 0
    assert len(facts) == 1
    assert facts[0].known_at_source == "acceptance"
    assert facts[0].accepted_at.isoformat() == "2024-05-10T12:00:00+00:00"


def test_sync_preserves_raw_provider_cache_metadata(tmp_path, monkeypatch):
    store, _, service = setup_services(tmp_path)
    retrieved = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(service.sec, "company_facts", lambda _: company_facts_envelope(retrieved))
    monkeypatch.setattr(service.sec, "submissions", lambda _: submissions_envelope(retrieved))

    result = service.sync_company_facts("NVDA")

    cached_facts = store.load_provider_payload("SEC EDGAR", "sec_company_facts", "0001045810")
    cached_submissions = store.load_provider_payload("SEC EDGAR", "sec_submissions", "0001045810")
    assert result.observations_inserted == 3
    assert cached_facts["metadata"]["knownAt"] == retrieved.isoformat()
    assert cached_submissions["metadata"]["source"] == "SEC EDGAR"


def test_sync_uses_stale_provider_cache_without_rewriting_facts(tmp_path, monkeypatch):
    _, _, service = setup_services(tmp_path)
    retrieved = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(service.sec, "company_facts", lambda _: company_facts_envelope(retrieved))
    monkeypatch.setattr(service.sec, "submissions", lambda _: submissions_envelope(retrieved))
    service.sync_company_facts("NVDA")

    def unavailable(_):
        raise ProviderUnavailable("SEC EDGAR is unavailable for this test.")

    monkeypatch.setattr(service.sec, "company_facts", unavailable)
    monkeypatch.setattr(service.sec, "submissions", unavailable)
    repeated = service.sync_company_facts("NVDA")

    assert repeated.observations_inserted == 0
    assert len(service.history("NVDA")) == 3
