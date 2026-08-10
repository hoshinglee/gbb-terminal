import hashlib
from datetime import date, datetime, timezone

import pytest
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from gbb_terminal.api.routes.intelligence import create_intelligence_router
from gbb_terminal.api.schemas.v3 import ProvenanceResponse
from gbb_terminal.intelligence import (
    CompanyIdentityRepository,
    CompanyIdentityService,
    CompanyIntelligenceService,
    CompanyProvenance,
    CompanyRegistration,
    FinancialFact,
    FinancialFactRepository,
    FinancialFactService,
    NormalizedMetricsService,
    HistoricalValuationService,
    ValuationRepository,
    EarningsIntelligenceService,
    EarningsRepository,
)
from gbb_terminal.market_data.providers.sec import SECProvider
from gbb_terminal.storage.database import LocalMarketStore


def build_client(tmp_path):
    store = LocalMarketStore(tmp_path / "v3-api.duckdb")
    sec = SECProvider()
    identity_repository = CompanyIdentityRepository(store.connection)
    identities = CompanyIdentityService(identity_repository, sec)
    observed = datetime(2024, 1, 2, 12, tzinfo=timezone.utc)
    company = identity_repository.upsert_company(
        CompanyRegistration(
            cik="1045810",
            legal_name="NVIDIA CORP",
            primary_ticker="NVDA",
            exchange="Nasdaq",
            sector="Technology",
            industry="Semiconductors",
            fiscal_year_end="0128",
            effective_from=date(1999, 1, 22),
            provenance=CompanyProvenance(
                source="SEC EDGAR",
                dataset="sec_company_tickers",
                observation_timestamp=observed,
                known_at=observed,
                retrieved_at=observed,
                status="Delayed",
                quality_warnings=["Directory scope is not guaranteed."],
            ),
        )
    )
    fact_repository = FinancialFactRepository(store.connection)
    for value, accession, known_at, form in [
        (100, "0001045810-24-000001", datetime(2024, 2, 20, 21, tzinfo=timezone.utc), "10-K"),
        (110, "0001045810-25-000002", datetime(2025, 3, 1, 16, tzinfo=timezone.utc), "10-K/A"),
    ]:
        fact_id = hashlib.sha256(accession.encode()).hexdigest()
        fact_repository.save_facts(
            [
                FinancialFact(
                    fact_id=fact_id,
                    company_id=company.company_id,
                    cik=company.cik,
                    taxonomy="us-gaap",
                    concept="RevenueFromContractWithCustomerExcludingAssessedTax",
                    label="Revenue",
                    value=value,
                    raw_value=str(value),
                    unit="USD",
                    period_start=date(2023, 1, 1),
                    period_end=date(2023, 12, 31),
                    fiscal_year=2023,
                    fiscal_period="FY",
                    form=form,
                    filed_date=known_at.date(),
                    accepted_at=known_at,
                    known_at_source="acceptance",
                    accession_number=accession,
                    frame="CY2023",
                    provenance=CompanyProvenance(
                        source="SEC EDGAR",
                        dataset="sec_company_facts",
                        observation_timestamp=datetime(2023, 12, 31, tzinfo=timezone.utc),
                        known_at=known_at,
                        retrieved_at=known_at,
                        status="Delayed",
                    ),
                    source_metadata={"accessionNumber": accession},
                )
            ]
        )
    facts = FinancialFactService(fact_repository, identities, store, sec)
    metrics = NormalizedMetricsService(facts, identities)
    valuation = HistoricalValuationService(metrics, ValuationRepository(store.connection))
    earnings = EarningsIntelligenceService(metrics, EarningsRepository(store.connection))

    class FixtureMarketData:
        metadata = {
            "NVDA": {
                "source": "Yahoo Finance",
                "qualityWarnings": ["Fixture delayed prices."],
            }
        }

        async def history(self, ticker, period):
            return pd.DataFrame(
                {"Close": [100.0, 105.0]},
                index=pd.to_datetime(["2024-03-01", "2024-03-08"]),
            )

    service = CompanyIntelligenceService(
        identities,
        facts,
        metrics,
        valuation,
        FixtureMarketData(),
        earnings,
    )
    app = FastAPI()
    app.include_router(create_intelligence_router(service))
    return TestClient(app), company


def test_company_overview_uses_canonical_identity_and_provenance(tmp_path):
    client, company = build_client(tmp_path)

    response = client.get("/api/v3/companies/nvda")

    assert response.status_code == 200
    payload = response.json()
    assert payload["apiVersion"] == "v3"
    assert payload["companyId"] == company.company_id
    assert payload["cik"] == "0001045810"
    assert payload["primaryTicker"] == "NVDA"
    assert payload["provenance"]["source"] == "SEC EDGAR"
    assert payload["securities"][0]["validFrom"] == "1999-01-22"


def test_financial_history_respects_as_of_and_keeps_source_metadata(tmp_path):
    client, _ = build_client(tmp_path)

    response = client.get(
        "/api/v3/companies/NVDA/financials",
        params={
            "concepts": "RevenueFromContractWithCustomerExcludingAssessedTax",
            "as_of": "2024-12-31T23:59:00+00:00",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matchingFactCount"] == 1
    assert payload["returnedFactCount"] == 1
    assert payload["facts"][0]["value"] == 100
    assert payload["facts"][0]["accessionNumber"] == "0001045810-24-000001"
    assert payload["facts"][0]["provenance"]["knownAt"] == "2024-02-20T21:00:00Z"


def test_metrics_endpoint_returns_versioned_lineage_under_as_of_boundary(tmp_path):
    client, _ = build_client(tmp_path)

    response = client.get(
        "/api/v3/companies/NVDA/metrics",
        params={"period": "annual", "as_of": "2024-12-31T23:59:00+00:00"},
    )

    assert response.status_code == 200
    payload = response.json()
    revenue = next(metric for metric in payload["metrics"] if metric["metricId"] == "revenue")
    assert revenue["value"] == 100
    assert revenue["definitionVersion"] == "1.1.0"
    assert revenue["sourceFactIds"] == payload["provenance"]["sourceFactIds"]
    assert payload["periodKind"] == "annual"
    assert payload["provenance"]["dataset"] == "normalized_financial_metrics"


def test_v3_query_and_response_schemas_reject_unknown_fields(tmp_path):
    client, _ = build_client(tmp_path)

    response = client.get("/api/v3/companies/NVDA/metrics", params={"unexpected": "value"})

    assert response.status_code == 422
    overview_schema = client.app.openapi()["components"]["schemas"]["CompanyOverviewResponse"]
    assert overview_schema["additionalProperties"] is False
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ProvenanceResponse.model_validate(
            {
                "source": "SEC EDGAR",
                "dataset": "fixture",
                "observation_timestamp": "2024-01-01T00:00:00Z",
                "known_at": "2024-01-01T00:00:00Z",
                "retrieved_at": "2024-01-01T00:00:00Z",
                "status": "Delayed",
                "cached": False,
                "unexpected": True,
            }
        )


def test_unknown_company_returns_not_found(tmp_path):
    client, _ = build_client(tmp_path)

    response = client.get("/api/v3/companies/UNKNOWN")

    assert response.status_code == 404


def test_valuation_endpoint_returns_versioned_history_statistics_and_provenance(tmp_path):
    client, _ = build_client(tmp_path)

    response = client.get(
        "/api/v3/companies/NVDA/valuation",
        params={"period": "1y", "frequency": "weekly", "metrics": "trailing_pe"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["apiVersion"] == "v3"
    assert payload["frequency"] == "weekly"
    assert len(payload["history"]["trailing_pe"]) == 2
    assert payload["statistics"]["trailing_pe"]["status"] == "unavailable"
    assert payload["provenance"]["priceSource"] == "Yahoo Finance"
    assert payload["provenance"]["fundamentalSource"] == "SEC EDGAR"
    assert payload["provenance"]["engineVersion"] == "1.0.0"


def test_earnings_endpoint_returns_event_evidence_reactions_and_sample_size(tmp_path):
    client, _ = build_client(tmp_path)

    response = client.get("/api/v3/companies/NVDA/earnings", params={"benchmark": "spy"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["apiVersion"] == "v3"
    assert payload["benchmarkTicker"] == "SPY"
    assert len(payload["events"]) == 1
    assert payload["events"][0]["event"]["evidence"]["source"] == "SEC EDGAR"
    assert payload["events"][0]["reaction"]["windows"]["d20"]["status"] == "insufficient_data"
    assert payload["aggregate"]["sampleSize"] == 0
    assert payload["aggregate"]["excludedEvents"] == 1
    assert payload["provenance"]["eventModelVersion"] == "1.0.0"
    assert "do not predict" in " ".join(payload["warnings"])
