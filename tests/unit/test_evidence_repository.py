import hashlib
from datetime import date, datetime, timezone

import pytest

from gbb_terminal.intelligence import (
    CompanyIdentityRepository,
    CompanyProvenance,
    CompanyRegistration,
    EvidenceClaimLinkCreate,
    EvidenceDocumentCreate,
    EvidenceDocumentQuery,
    EvidenceDocumentType,
    EvidenceParseStatus,
    EvidenceRepository,
    EvidenceSpanCreate,
)
from gbb_terminal.storage.database import LocalMarketStore


def build_repository(tmp_path):
    store = LocalMarketStore(tmp_path / "evidence.duckdb")
    identities = CompanyIdentityRepository(store.connection)
    observed = datetime(2024, 1, 2, 12, tzinfo=timezone.utc)
    company = identities.upsert_company(
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
    return company, EvidenceRepository(store.connection)


def document_create(company_id, content, known_at, external_id="0001045810-24-000001"):
    return EvidenceDocumentCreate(
        company_id=company_id,
        source="SEC EDGAR",
        dataset="sec_filing_documents",
        document_type=EvidenceDocumentType.FORM_10_K,
        external_id=external_id,
        title="NVIDIA 2024 Form 10-K",
        form="10-k",
        accession_number=external_id,
        source_url=f"https://www.sec.gov/Archives/{external_id}",
        filed_at=known_at,
        known_at=known_at,
        retrieved_at=known_at,
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        source_metadata={"original": True},
    )


def span_create(document_id, text, start=100):
    return EvidenceSpanCreate(
        document_id=document_id,
        exact_text=text,
        section="Item 1. Business",
        page_number=8,
        start_offset=start,
        end_offset=start + len(text),
        extraction_method="deterministic_fixture",
        extracted_at=datetime(2024, 2, 22, 12, tzinfo=timezone.utc),
    )


def test_documents_deduplicate_exact_content_and_version_changed_content(tmp_path):
    company, repository = build_repository(tmp_path)
    first_known = datetime(2024, 2, 21, 21, tzinfo=timezone.utc)
    first = repository.save_document(document_create(company.company_id, "first filing body", first_known))
    duplicate = repository.save_document(document_create(company.company_id, "first filing body", first_known))
    revised = repository.save_document(
        document_create(
            company.company_id,
            "amended filing body",
            datetime(2024, 2, 22, 21, tzinfo=timezone.utc),
        )
    )

    assert duplicate.document_id == first.document_id
    assert repository.count_documents(company.company_id) == 2
    assert first.version == 1
    assert revised.version == 2
    assert revised.supersedes_document_id == first.document_id
    assert repository.get_document(first.document_id).known_at == first_known
    assert repository.get_document(first.document_id).source_metadata == {"original": True}


def test_document_queries_respect_known_at_and_document_type(tmp_path):
    company, repository = build_repository(tmp_path)
    first_known = datetime(2024, 2, 21, 21, tzinfo=timezone.utc)
    repository.save_document(document_create(company.company_id, "first filing", first_known))
    repository.save_document(
        document_create(
            company.company_id,
            "future amendment",
            datetime(2025, 2, 21, 21, tzinfo=timezone.utc),
        )
    )

    documents = repository.list_documents(
        company.company_id,
        EvidenceDocumentQuery(
            document_types=[EvidenceDocumentType.FORM_10_K],
            as_of=datetime(2024, 12, 31, 23, tzinfo=timezone.utc),
        ),
    )

    assert len(documents) == 1
    assert documents[0].known_at == first_known


def test_spans_are_independently_retrievable_and_multiple_spans_support_one_claim(tmp_path):
    company, repository = build_repository(tmp_path)
    document = repository.save_document(
        document_create(
            company.company_id,
            "customer and supplier disclosure",
            datetime(2024, 2, 21, 21, tzinfo=timezone.utc),
        )
    )
    first = repository.save_span(span_create(document.document_id, "Customer A represented 13% of revenue."))
    duplicate = repository.save_span(span_create(document.document_id, "Customer A represented 13% of revenue."))
    second = repository.save_span(
        span_create(document.document_id, "We depend on a limited number of foundry suppliers.", start=500)
    )
    repository.link_claim(
        EvidenceClaimLinkCreate(claim_type="relationship", claim_id="customer-a", span_id=first.span_id)
    )
    repository.link_claim(
        EvidenceClaimLinkCreate(claim_type="relationship", claim_id="customer-a", span_id=second.span_id)
    )

    claim_evidence = repository.list_claim_spans(company.company_id, "relationship", "customer-a")

    assert duplicate.span_id == first.span_id
    assert repository.get_span(first.span_id).exact_text == first.exact_text
    assert [span.span_id for span in repository.list_spans(document.document_id)] == [first.span_id, second.span_id]
    assert {item.span.span_id for item in claim_evidence} == {first.span_id, second.span_id}
    assert {item.link.role.value for item in claim_evidence} == {"support"}
    assert repository.get_document(document.document_id).parse_status == EvidenceParseStatus.PARSED


def test_failed_parsing_cannot_create_evidence_spans(tmp_path):
    company, repository = build_repository(tmp_path)
    document = repository.save_document(
        document_create(
            company.company_id,
            "malformed document",
            datetime(2024, 2, 21, 21, tzinfo=timezone.utc),
        )
    )

    failed = repository.mark_parse_failed(document.document_id, "Parser could not locate a readable document body.")

    assert failed.parse_status == EvidenceParseStatus.FAILED
    with pytest.raises(ValueError, match="failed parsing"):
        repository.save_span(span_create(document.document_id, "Unsupported claim text"))


def test_document_and_span_timestamps_cannot_precede_source_availability(tmp_path):
    company, repository = build_repository(tmp_path)
    known_at = datetime(2024, 2, 21, 21, tzinfo=timezone.utc)
    invalid_document = document_create(company.company_id, "future retrieval", known_at).model_dump()
    invalid_document["retrieved_at"] = datetime(2024, 2, 20, 21, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="retrieved_at"):
        EvidenceDocumentCreate.model_validate(invalid_document)

    document = repository.save_document(document_create(company.company_id, "valid source", known_at))
    with pytest.raises(ValueError, match="document retrieval"):
        repository.save_span(
            span_create(document.document_id, "Premature extraction").model_copy(
                update={"extracted_at": datetime(2024, 2, 20, 21, tzinfo=timezone.utc)}
            )
        )
