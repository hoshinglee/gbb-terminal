import hashlib
from datetime import date, datetime, timezone

import pytest

from gbb_terminal.intelligence import (
    CompanyIdentityRepository,
    CompanyIdentityService,
    CompanyProvenance,
    CompanyRegistration,
    EvidenceDocumentCreate,
    EvidenceDocumentType,
    EvidenceRepository,
    EvidenceSpanCreate,
)
from gbb_terminal.intelligence.relationship_models import (
    RelationshipCandidate,
    RelationshipConfidence,
    RelationshipDirection,
    RelationshipNetworkQuery,
    RelationshipObservationKind,
    RelationshipOverrideCreate,
    RelationshipType,
)
from gbb_terminal.intelligence.relationship_repository import RelationshipRepository
from gbb_terminal.intelligence.relationships import RelationshipService
from gbb_terminal.storage.database import LocalMarketStore


def register_company(repository, cik, name, ticker):
    observed = datetime(2024, 1, 2, 12, tzinfo=timezone.utc)
    return repository.upsert_company(
        CompanyRegistration(
            cik=cik,
            legal_name=name,
            primary_ticker=ticker,
            exchange="Nasdaq",
            effective_from=date(2000, 1, 1),
            provenance=CompanyProvenance(
                source="SEC EDGAR",
                dataset="sec_company_tickers",
                observation_timestamp=observed,
                known_at=observed,
                retrieved_at=observed,
            ),
        )
    )


def build_services(tmp_path):
    store = LocalMarketStore(tmp_path / "relationships.duckdb")
    identity_repository = CompanyIdentityRepository(store.connection)
    nvda = register_company(identity_repository, "1045810", "NVIDIA Corporation", "NVDA")
    tsm = register_company(
        identity_repository,
        "1046179",
        "Taiwan Semiconductor Manufacturing Company Limited",
        "TSM",
    )
    msft = register_company(identity_repository, "789019", "Microsoft Corporation", "MSFT")
    evidence = EvidenceRepository(store.connection)
    repository = RelationshipRepository(store.connection, evidence)
    identities = CompanyIdentityService(identity_repository, None)
    return nvda, tsm, msft, evidence, repository, RelationshipService(repository, evidence, identities)


def evidence_span(evidence, company_id, text, known_at, external_id, start_offset=0):
    document = evidence.save_document(
        EvidenceDocumentCreate(
            company_id=company_id,
            source="SEC EDGAR",
            dataset="sec_filing_documents",
            document_type=EvidenceDocumentType.FORM_10_K,
            external_id=external_id,
            title="Source Relationship Disclosure",
            form="10-K",
            accession_number=external_id,
            source_url=f"https://www.sec.gov/Archives/{external_id}",
            filed_at=known_at,
            known_at=known_at,
            retrieved_at=known_at,
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
        )
    )
    return evidence.save_span(
        EvidenceSpanCreate(
            document_id=document.document_id,
            exact_text=text,
            section="Item 1. Business",
            page_number=8,
            start_offset=start_offset,
            end_offset=start_offset + len(text),
            extraction_method="deterministic_fixture",
            extracted_at=known_at,
        )
    )


def test_deterministic_extraction_resolves_named_and_preserves_unnamed_counterparties(tmp_path):
    nvda, tsm, msft, evidence, repository, service = build_services(tmp_path)
    known_at = datetime(2024, 2, 21, 21, tzinfo=timezone.utc)
    span = evidence_span(
        evidence,
        nvda.company_id,
        "Taiwan Semiconductor Manufacturing Company Limited serves as our foundry. "
        "Microsoft Corporation is our customer. "
        "Customer A represented 13% of our revenue. "
        "Acme Systems serves as our supplier.",
        known_at,
        "0001045810-24-000001",
    )

    extracted = service.extract_span("NVDA", span.span_id)

    assert len(extracted) == 4
    by_name = {record.edge.raw_counterparty_name: record for record in extracted}
    assert by_name["Taiwan Semiconductor Manufacturing Company Limited"].target_company.company_id == tsm.company_id
    assert by_name["Microsoft Corporation"].target_company.company_id == msft.company_id
    assert by_name["Customer A"].target_company is None
    assert by_name["Customer A"].observation.exposure_value == 13
    assert by_name["Customer A"].edge.relationship_type == RelationshipType.CUSTOMER_CONCENTRATION
    assert by_name["Acme Systems"].target_company is None
    assert repository.count_edges() == 4
    assert all(record.evidence for record in extracted)
    incoming = service.network("TSM", RelationshipNetworkQuery(as_of=known_at))
    assert incoming.relationships[0].source_company.company_id == nvda.company_id
    assert incoming.relationships[0].perspective_direction == RelationshipDirection.DOWNSTREAM


def test_duplicate_evidence_accumulates_without_duplicate_economic_edge(tmp_path):
    nvda, tsm, _, evidence, repository, service = build_services(tmp_path)
    known_at = datetime(2024, 2, 21, 21, tzinfo=timezone.utc)
    first_span = evidence_span(
        evidence,
        nvda.company_id,
        "Taiwan Semiconductor Manufacturing Company Limited serves as our foundry.",
        known_at,
        "0001045810-24-000002",
    )
    second_span = evidence.save_span(
        EvidenceSpanCreate(
            document_id=first_span.document_id,
            exact_text="We depend on this foundry for advanced process capacity.",
            section="Item 1A. Risk Factors",
            page_number=19,
            start_offset=400,
            end_offset=453,
            extraction_method="deterministic_fixture",
            extracted_at=known_at,
        )
    )
    base = dict(
        source_company_id=nvda.company_id,
        target_company_id=tsm.company_id,
        raw_counterparty_name="Taiwan Semiconductor Manufacturing Company Limited",
        relationship_type=RelationshipType.MANUFACTURER_FOUNDRY,
        direction=RelationshipDirection.UPSTREAM,
        known_at=known_at,
        extraction_method="deterministic_relationship_rules_v1",
        confidence=RelationshipConfidence.DISCLOSED,
    )

    edge, first = repository.save_candidate(RelationshipCandidate(**base, evidence_span_ids=[first_span.span_id]))
    duplicate_edge, duplicate = repository.save_candidate(
        RelationshipCandidate(**base, evidence_span_ids=[second_span.span_id])
    )
    history = service.history("NVDA", edge.relationship_id)

    assert duplicate_edge.relationship_id == edge.relationship_id
    assert duplicate.observation_id == first.observation_id
    assert repository.count_edges() == 1
    assert repository.count_observations() == 1
    assert len(history.evidence[first.observation_id]) == 2


def test_relationship_expiry_and_human_override_remain_point_in_time_and_auditable(tmp_path):
    nvda, tsm, _, evidence, repository, service = build_services(tmp_path)
    first_known = datetime(2024, 2, 21, 21, tzinfo=timezone.utc)
    first_span = evidence_span(
        evidence,
        nvda.company_id,
        "Taiwan Semiconductor Manufacturing Company Limited serves as our foundry.",
        first_known,
        "0001045810-24-000003",
    )
    edge, original = repository.save_candidate(
        RelationshipCandidate(
            source_company_id=nvda.company_id,
            target_company_id=tsm.company_id,
            raw_counterparty_name="Taiwan Semiconductor Manufacturing Company Limited",
            relationship_type=RelationshipType.MANUFACTURER_FOUNDRY,
            direction=RelationshipDirection.UPSTREAM,
            valid_from=date(2024, 1, 1),
            known_at=first_known,
            extraction_method="deterministic_relationship_rules_v1",
            confidence=RelationshipConfidence.DISCLOSED,
            evidence_span_ids=[first_span.span_id],
        )
    )
    correction_known = datetime(2025, 2, 21, 21, tzinfo=timezone.utc)
    correction_span = evidence_span(
        evidence,
        nvda.company_id,
        "The earlier foundry arrangement ended during fiscal 2024.",
        correction_known,
        "0001045810-25-000003",
    )

    corrected = service.override(
        "NVDA",
        edge.relationship_id,
        RelationshipOverrideCreate(
            target_company_id=tsm.company_id,
            valid_from=date(2024, 1, 1),
            valid_to=date(2024, 12, 31),
            known_at=correction_known,
            confidence=RelationshipConfidence.DISCLOSED,
            evidence_span_ids=[correction_span.span_id],
            correction_note="Local correction after a later explicit disclosure.",
        ),
    )

    historical = service.network(
        "NVDA",
        RelationshipNetworkQuery(as_of=datetime(2024, 6, 1, tzinfo=timezone.utc)),
    )
    current = service.network(
        "NVDA",
        RelationshipNetworkQuery(as_of=datetime(2025, 6, 1, tzinfo=timezone.utc)),
    )
    history = service.history("NVDA", edge.relationship_id)

    assert [item.observation.observation_id for item in historical.relationships] == [original.observation_id]
    assert current.relationships == []
    assert corrected.observation.observation_kind == RelationshipObservationKind.HUMAN_OVERRIDE
    assert corrected.observation.supersedes_observation_id == original.observation_id
    assert corrected.observation.correction_note.startswith("Local correction")
    assert len(history.observations) == 2


def test_relationship_observation_cannot_precede_source_availability(tmp_path):
    nvda, tsm, _, evidence, repository, _ = build_services(tmp_path)
    evidence_known = datetime(2025, 2, 21, 21, tzinfo=timezone.utc)
    span = evidence_span(
        evidence,
        nvda.company_id,
        "Taiwan Semiconductor Manufacturing Company Limited serves as our foundry.",
        evidence_known,
        "0001045810-25-000004",
    )

    with pytest.raises(ValueError, match="cannot precede its source evidence"):
        repository.save_candidate(
            RelationshipCandidate(
                source_company_id=nvda.company_id,
                target_company_id=tsm.company_id,
                raw_counterparty_name="Taiwan Semiconductor Manufacturing Company Limited",
                relationship_type=RelationshipType.MANUFACTURER_FOUNDRY,
                direction=RelationshipDirection.UPSTREAM,
                known_at=datetime(2024, 2, 21, 21, tzinfo=timezone.utc),
                extraction_method="deterministic_relationship_rules_v1",
                confidence=RelationshipConfidence.DISCLOSED,
                evidence_span_ids=[span.span_id],
            )
        )
