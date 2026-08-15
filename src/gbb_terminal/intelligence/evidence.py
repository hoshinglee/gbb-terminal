from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .evidence_models import EvidenceClaimSpan, EvidenceDocument, EvidenceDocumentQuery, EvidenceSpan
from .evidence_repository import EvidenceRepository
from .models import CompanyIdentity
from .service import CompanyIdentityService


@dataclass(frozen=True)
class CompanyEvidenceDocuments:
    company: CompanyIdentity
    as_of: datetime
    documents: list[EvidenceDocument]
    matching_document_count: int
    warnings: list[str]


@dataclass(frozen=True)
class CompanyEvidenceDocument:
    company: CompanyIdentity
    as_of: datetime
    document: EvidenceDocument
    spans: list[EvidenceSpan]


@dataclass(frozen=True)
class CompanyEvidenceSpan:
    company: CompanyIdentity
    as_of: datetime
    document: EvidenceDocument
    span: EvidenceSpan


@dataclass(frozen=True)
class CompanyClaimEvidence:
    company: CompanyIdentity
    as_of: datetime
    claim_type: str
    claim_id: str
    evidence: list[EvidenceClaimSpan]
    warnings: list[str]


class EvidenceService:
    def __init__(self, repository: EvidenceRepository, identities: CompanyIdentityService) -> None:
        self.repository = repository
        self.identities = identities

    def documents(self, ticker: str, query: EvidenceDocumentQuery) -> CompanyEvidenceDocuments:
        company = self._company(ticker)
        effective_as_of = (query.as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
        effective_query = query.model_copy(update={"as_of": effective_as_of})
        matching_count = self.repository.count_documents(company.company_id, effective_query)
        documents = self.repository.list_documents(company.company_id, effective_query)
        warnings = []
        if matching_count > len(documents):
            warnings.append(
                f"The response contains the first {len(documents)} of {matching_count} matching evidence documents."
            )
        if not documents:
            warnings.append(
                "No source documents are available inside this as-of boundary; public disclosure coverage is incomplete."
            )
        return CompanyEvidenceDocuments(company, effective_as_of, documents, matching_count, warnings)

    def document(
        self,
        ticker: str,
        document_id: str,
        as_of: datetime | None = None,
    ) -> CompanyEvidenceDocument:
        company = self._company(ticker)
        effective_as_of = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
        document = self.repository.get_document(document_id)
        if document is None or document.company_id != company.company_id or document.known_at > effective_as_of:
            raise LookupError(f"No evidence document {document_id} is available for {ticker.upper()} as of this boundary.")
        return CompanyEvidenceDocument(
            company=company,
            as_of=effective_as_of,
            document=document,
            spans=self.repository.list_spans(document_id),
        )

    def span(self, ticker: str, span_id: str, as_of: datetime | None = None) -> CompanyEvidenceSpan:
        company = self._company(ticker)
        effective_as_of = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
        span = self.repository.get_span(span_id)
        document = self.repository.get_document(span.document_id) if span else None
        if (
            span is None
            or document is None
            or document.company_id != company.company_id
            or document.known_at > effective_as_of
        ):
            raise LookupError(f"No evidence span {span_id} is available for {ticker.upper()} as of this boundary.")
        return CompanyEvidenceSpan(company, effective_as_of, document, span)

    def claim(
        self,
        ticker: str,
        claim_type: str,
        claim_id: str,
        as_of: datetime | None = None,
    ) -> CompanyClaimEvidence:
        company = self._company(ticker)
        effective_as_of = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
        evidence = self.repository.list_claim_spans(
            company.company_id,
            claim_type,
            claim_id,
            effective_as_of,
        )
        warnings = [] if evidence else ["No source-backed evidence spans are attached to this claim as of the boundary."]
        return CompanyClaimEvidence(company, effective_as_of, claim_type, claim_id, evidence, warnings)

    def _company(self, ticker: str) -> CompanyIdentity:
        company = self.identities.resolve_ticker(ticker)
        if company is None:
            raise LookupError(f"No canonical company identity exists for ticker {ticker.upper()}.")
        return company
