import hashlib
import time
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
    EvidenceClaimLinkCreate,
    EvidenceDocumentCreate,
    EvidenceDocumentType,
    EvidenceRepository,
    EvidenceService,
    EvidenceSpanCreate,
    GuidanceComparison,
    GuidanceRepository,
    GuidanceService,
    GuidanceStatementCreate,
    GuidanceStatementType,
    GuidanceValueKind,
    OperatingMetricCategory,
    OperatingMetricDefinitionCreate,
    OperatingMetricObservationCreate,
    OperatingValueType,
    OperationsIntelligenceService,
    OperationsRepository,
    RelationshipCandidate,
    RelationshipConfidence,
    RelationshipDirection,
    RelationshipRepository,
    RelationshipService,
    RelationshipType,
)
from gbb_terminal.intelligence.collection_models import CollectorDiscovery
from gbb_terminal.intelligence.collection_repository import IntelligenceRefreshRepository
from gbb_terminal.intelligence.collection_service import IntelligenceRefreshService
from gbb_terminal.intelligence.document_extraction import DocumentExtractionService
from gbb_terminal.intelligence.document_parser import PublicDocumentParser
from gbb_terminal.intelligence.estimates import EstimateIntelligenceService
from gbb_terminal.market_data.providers.sec import SECProvider
from gbb_terminal.market_data.providers.estimates import EmptyEstimateProvider
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
    estimates = EstimateIntelligenceService(metrics, EmptyEstimateProvider())
    evidence_repository = EvidenceRepository(store.connection)
    evidence = EvidenceService(evidence_repository, identities)
    evidence_document = evidence_repository.save_document(
        EvidenceDocumentCreate(
            company_id=company.company_id,
            source="SEC EDGAR",
            dataset="sec_filing_documents",
            document_type=EvidenceDocumentType.FORM_10_K,
            external_id="0001045810-24-000001",
            title="NVIDIA 2024 Form 10-K",
            form="10-K",
            accession_number="0001045810-24-000001",
            source_url="https://www.sec.gov/Archives/0001045810-24-000001",
            filed_at=observed,
            known_at=observed,
            retrieved_at=observed,
            content_hash=hashlib.sha256(b"fixture filing body").hexdigest(),
            source_metadata={"fixture": True},
        )
    )
    evidence_span = evidence_repository.save_span(
        EvidenceSpanCreate(
            document_id=evidence_document.document_id,
            exact_text="One customer represented more than ten percent of revenue.",
            section="Item 1. Business",
            page_number=9,
            start_offset=120,
            end_offset=177,
            extraction_method="deterministic_fixture",
            extracted_at=observed,
        )
    )
    evidence_repository.link_claim(
        EvidenceClaimLinkCreate(
            claim_type="relationship",
            claim_id="major-customer",
            span_id=evidence_span.span_id,
        )
    )
    operations_span = evidence_repository.save_span(
        EvidenceSpanCreate(
            document_id=evidence_document.document_id,
            exact_text="Data Center revenue was 75 million dollars for fiscal 2024.",
            section="Note 17. Segment Information",
            page_number=84,
            start_offset=500,
            end_offset=560,
            extraction_method="deterministic_fixture",
            extracted_at=observed,
        )
    )
    guidance_span = evidence_repository.save_span(
        EvidenceSpanCreate(
            document_id=evidence_document.document_id,
            exact_text="Revenue is expected to be between $100 million and $110 million.",
            section="Outlook",
            page_number=3,
            start_offset=700,
            end_offset=765,
            extraction_method="deterministic_fixture",
            extracted_at=observed,
        )
    )
    relationship_repository = RelationshipRepository(store.connection, evidence_repository)
    relationship_repository.save_candidate(
        RelationshipCandidate(
            source_company_id=company.company_id,
            raw_counterparty_name="Customer A",
            relationship_type=RelationshipType.CUSTOMER_CONCENTRATION,
            direction=RelationshipDirection.DOWNSTREAM,
            exposure_value=13,
            exposure_unit="% of revenue",
            known_at=observed,
            extraction_method="deterministic_fixture",
            confidence=RelationshipConfidence.DISCLOSED,
            evidence_span_ids=[evidence_span.span_id],
        )
    )
    relationships = RelationshipService(relationship_repository, evidence_repository, identities)
    operations_repository = OperationsRepository(store.connection, evidence_repository)
    segment = operations_repository.save_definition(
        OperatingMetricDefinitionCreate(
            company_id=company.company_id,
            category=OperatingMetricCategory.SEGMENT,
            definition_key="data_center",
            label="Data Center",
            measure="revenue",
            unit="USD millions",
            value_type=OperatingValueType.CURRENCY,
            reporting_basis="segments-v1",
            known_at=observed,
            extraction_method="deterministic_fixture",
            evidence_span_ids=[operations_span.span_id],
        )
    )
    operations_repository.save_observation(
        OperatingMetricObservationCreate(
            definition_id=segment.definition_id,
            period_end=date(2024, 1, 28),
            fiscal_year=2024,
            fiscal_period="FY",
            value=75,
            unit="USD millions",
            known_at=observed,
            extraction_method="deterministic_fixture",
            evidence_span_ids=[operations_span.span_id],
        )
    )
    operations = OperationsIntelligenceService(operations_repository, evidence_repository, identities)
    guidance_repository = GuidanceRepository(store.connection, evidence_repository)
    guidance_repository.save_statement(
        GuidanceStatementCreate(
            company_id=company.company_id,
            statement_type=GuidanceStatementType.FINANCIAL_GUIDANCE,
            topic="Quarterly Revenue",
            metric_id="revenue",
            statement_text="Revenue is expected to be between $100 million and $110 million.",
            value_kind=GuidanceValueKind.NUMERIC_RANGE,
            comparison=GuidanceComparison.WITHIN_RANGE,
            lower_bound=100,
            upper_bound=110,
            unit="USD millions",
            applicable_period_end=date(2024, 4, 28),
            fiscal_year=2025,
            fiscal_period="Q1",
            issued_at=observed,
            known_at=observed,
            extraction_method="deterministic_fixture",
            evidence_span_ids=[guidance_span.span_id],
        )
    )
    guidance = GuidanceService(guidance_repository, evidence_repository, identities, metrics)

    class EmptyCollector:
        def discover(self, company, request):
            return CollectorDiscovery()

        def download(self, company, document):
            raise AssertionError("An empty collector must not download documents.")

    source_refresh = IntelligenceRefreshService(
        identities,
        evidence_repository,
        IntelligenceRefreshRepository(store.connection),
        EmptyCollector(),
        PublicDocumentParser(),
        DocumentExtractionService(
            evidence_repository,
            relationships,
            operations_repository,
            guidance_repository,
        ),
        relationship_repository,
        operations_repository,
        guidance_repository,
    )

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
        estimates,
        evidence,
        relationships,
        operations,
        guidance,
        source_refresh,
    )
    app = FastAPI()
    app.include_router(create_intelligence_router(service, store))
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
    assert revenue["definitionVersion"] == "1.2.0"
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


def test_source_refresh_job_and_health_distinguish_no_disclosure(tmp_path):
    client, company = build_client(tmp_path)

    initial = client.get("/api/v3/companies/NVDA/sources/health")
    assert initial.status_code == 200
    assert initial.json()["companyId"] == company.company_id
    assert {item["status"] for item in initial.json()["coverage"]} == {"unavailable"}

    with client:
        accepted = client.post(
            "/api/v3/companies/NVDA/sources/refresh",
            json={"forms": ["10-K"], "maxFilings": 1, "includeExhibits": False},
        )
        assert accepted.status_code == 202
        job_id = accepted.json()["jobId"]
        for _ in range(100):
            job = client.get(f"/api/v3/intelligence-jobs/{job_id}")
            assert job.status_code == 200
            if job.json()["status"] != "running":
                break
            time.sleep(0.01)

    payload = job.json()
    assert payload["status"] == "completed"
    assert payload["result"]["status"] == "completed"
    assert payload["result"]["items"][0]["status"] == "no_disclosure"
    health = client.get("/api/v3/companies/NVDA/sources/health").json()
    assert {item["status"] for item in health["coverage"]} == {"populated"}
    assert health["lastRefresh"]["items"][0]["status"] == "no_disclosure"
    assert client.post("/api/v3/intelligence-jobs/missing/cancel").status_code == 404


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


def test_estimates_endpoint_is_empty_safe_and_distinguishes_expectations_from_reported_facts(tmp_path):
    client, _ = build_client(tmp_path)

    response = client.get("/api/v3/companies/NVDA/estimates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["apiVersion"] == "v3"
    assert payload["comparisons"] == []
    assert payload["providerKey"] == "none"
    assert payload["provenance"]["expectationDataset"] == "analyst_estimates"
    assert payload["provenance"]["reportedDataset"] == "normalized_financial_metrics"
    assert "not SEC-reported facts" in payload["provenance"]["distinction"]


def test_evidence_endpoints_preserve_source_context_as_of_boundaries_and_claim_links(tmp_path):
    client, _ = build_client(tmp_path)

    history = client.get("/api/v3/companies/NVDA/evidence/documents", params={"types": "10-k"})

    assert history.status_code == 200
    payload = history.json()
    assert payload["matchingDocumentCount"] == 1
    assert payload["documents"][0]["source"] == "SEC EDGAR"
    assert payload["documents"][0]["parseStatus"] == "parsed"
    assert payload["documents"][0]["knownAt"] == "2024-01-02T12:00:00Z"
    document_id = payload["documents"][0]["documentId"]

    detail = client.get(f"/api/v3/companies/NVDA/evidence/documents/{document_id}")
    assert detail.status_code == 200
    relationship_span = next(
        item for item in detail.json()["spans"] if item["exactText"].startswith("One customer")
    )
    span_id = relationship_span["spanId"]

    span = client.get(f"/api/v3/companies/NVDA/evidence/spans/{span_id}")
    assert span.status_code == 200
    assert span.json()["span"]["documentId"] == document_id
    assert span.json()["document"]["sourceUrl"].startswith("https://www.sec.gov/")

    claim = client.get("/api/v3/companies/NVDA/evidence/claims/relationship/major-customer")
    assert claim.status_code == 200
    assert [item["span"]["spanId"] for item in claim.json()["evidence"]] == [span_id]
    assert claim.json()["evidence"][0]["role"] == "support"

    before_publication = client.get(
        f"/api/v3/companies/NVDA/evidence/documents/{document_id}",
        params={"as_of": "2024-01-01T23:59:00+00:00"},
    )
    assert before_publication.status_code == 404

    invalid_type = client.get("/api/v3/companies/NVDA/evidence/documents", params={"types": "rumor"})
    assert invalid_type.status_code == 400


def test_relationship_endpoints_return_only_persisted_source_backed_edges_and_history(tmp_path):
    client, _ = build_client(tmp_path)

    response = client.get(
        "/api/v3/companies/NVDA/relationships",
        params={"directions": "downstream", "confidences": "disclosed"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matchingRelationshipCount"] == 1
    assert payload["relationships"][0]["edge"]["rawCounterpartyName"] == "Customer A"
    assert payload["relationships"][0]["targetCompany"] is None
    assert payload["relationships"][0]["observation"]["exposureValue"] == 13
    assert payload["relationships"][0]["evidence"][0]["span"]["exactText"].startswith("One customer")
    assert "incomplete" in " ".join(payload["warnings"])
    relationship_id = payload["relationships"][0]["edge"]["relationshipId"]

    history = client.get(f"/api/v3/companies/NVDA/relationships/{relationship_id}")
    assert history.status_code == 200
    assert len(history.json()["observations"]) == 1
    assert history.json()["evidence"][history.json()["observations"][0]["observationId"]]

    before_publication = client.get(
        "/api/v3/companies/NVDA/relationships",
        params={"as_of": "2024-01-01T23:59:00+00:00"},
    )
    assert before_publication.status_code == 200
    assert before_publication.json()["relationships"] == []
    assert client.get("/api/v3/companies/NVDA/relationships", params={"confidences": "certain"}).status_code == 400


def test_relationship_override_endpoint_is_strict_and_auditable(tmp_path):
    client, _ = build_client(tmp_path)
    relationship = client.get("/api/v3/companies/NVDA/relationships").json()["relationships"][0]
    relationship_id = relationship["edge"]["relationshipId"]
    span_id = relationship["evidence"][0]["span"]["spanId"]

    response = client.post(
        f"/api/v3/companies/NVDA/relationships/{relationship_id}/overrides",
        json={
            "targetCompanyId": None,
            "exposureValue": 15,
            "exposureUnit": "% of revenue",
            "knownAt": "2024-02-01T12:00:00Z",
            "confidence": "disclosed",
            "evidenceSpanIds": [span_id],
            "correctionNote": "Local review corrected the disclosed concentration value.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["observation"]["observationKind"] == "human_override"
    assert payload["observation"]["supersedesObservationId"] == relationship["observation"]["observationId"]
    assert payload["observation"]["correctionNote"].startswith("Local review")
    rejected = client.post(
        f"/api/v3/companies/NVDA/relationships/{relationship_id}/overrides",
        json={
            "knownAt": "2024-02-01T12:00:00Z",
            "confidence": "disclosed",
            "evidenceSpanIds": [span_id],
            "correctionNote": "Correction",
            "unexpected": True,
        },
    )
    assert rejected.status_code == 422


def test_operations_endpoint_preserves_reporting_basis_mix_and_source_context(tmp_path):
    client, _ = build_client(tmp_path)

    response = client.get("/api/v3/companies/NVDA/operations", params={"categories": "segment"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["series"][0]["definition"]["label"] == "Data Center"
    assert payload["series"][0]["definition"]["reportingBasis"] == "segments-v1"
    assert payload["series"][0]["points"][0]["mixPercent"] == 100
    assert payload["series"][0]["points"][0]["evidence"][0]["document"]["source"] == "SEC EDGAR"
    assert "non-standardized" in " ".join(payload["warnings"])
    assert client.get("/api/v3/companies/NVDA/operations", params={"categories": "division"}).status_code == 400


def test_guidance_endpoint_keeps_original_wording_status_and_evidence(tmp_path):
    client, _ = build_client(tmp_path)

    response = client.get(
        "/api/v3/companies/NVDA/guidance",
        params={"types": "financial_guidance", "statuses": "open"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["records"]) == 1
    record = payload["records"][0]
    assert record["status"] == "open"
    assert record["revisionDirection"] == "initial"
    assert record["statement"]["lowerBound"] == 100
    assert record["statement"]["upperBound"] == 110
    assert record["statementEvidence"][0]["span"]["exactText"] == record["statement"]["statementText"]
    assert "not forecasts" in " ".join(payload["warnings"])

    before_publication = client.get(
        "/api/v3/companies/NVDA/guidance",
        params={"as_of": "2024-01-01T23:59:00+00:00"},
    )
    assert before_publication.status_code == 200
    assert before_publication.json()["records"] == []
    assert client.get("/api/v3/companies/NVDA/guidance", params={"statuses": "accurate"}).status_code == 400
