from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from hashlib import sha256

from ..market_data.providers.base import ProviderUnavailable
from .collection_models import (
    DocumentCollectionStatus,
    IntelligenceRefreshRequest,
    IntelligenceRefreshStatus,
    IntelligenceRefreshSummary,
    IntelligenceSourceHealth,
    ModuleCoverage,
    ModuleCoverageStatus,
)
from .collection_repository import IntelligenceRefreshRepository
from .collectors.base import EvidenceCollector
from .document_extraction import DocumentExtractionService
from .document_parser import DOCUMENT_PARSER_VERSION, PublicDocumentParser, UnsupportedDocumentFormat
from .evidence_models import EvidenceDocumentCreate, EvidenceParseStatus
from .evidence_repository import EvidenceRepository
from .guidance_repository import GuidanceRepository
from .operations_repository import OperationsRepository
from .relationship_repository import RelationshipRepository
from .service import CompanyIdentityService


ProgressCallback = Callable[[float, str | None], None]
CancellationCheck = Callable[[], bool]


class IntelligenceRefreshService:
    def __init__(
        self,
        identities: CompanyIdentityService,
        evidence: EvidenceRepository,
        refreshes: IntelligenceRefreshRepository,
        collector: EvidenceCollector,
        parser: PublicDocumentParser,
        extraction: DocumentExtractionService,
        relationships: RelationshipRepository,
        operations: OperationsRepository,
        guidance: GuidanceRepository,
    ) -> None:
        self.identities = identities
        self.evidence = evidence
        self.refreshes = refreshes
        self.collector = collector
        self.parser = parser
        self.extraction = extraction
        self.relationships = relationships
        self.operations = operations
        self.guidance = guidance

    def refresh(
        self,
        ticker: str,
        request: IntelligenceRefreshRequest | None = None,
        progress: ProgressCallback | None = None,
        cancelled: CancellationCheck | None = None,
    ) -> IntelligenceRefreshSummary:
        command = request or IntelligenceRefreshRequest()
        symbol = ticker.strip().upper()
        company = self.identities.resolve_ticker(symbol)
        if company is None:
            self.identities.sync_sec_directory()
            company = self.identities.resolve_ticker(symbol)
        if company is None:
            raise LookupError(f"No canonical company identity exists for ticker {symbol} after SEC directory refresh.")
        refresh_id = self.refreshes.start(company.company_id, symbol, command)
        counts = {
            "documents_discovered": 0,
            "documents_downloaded": 0,
            "documents_unchanged": 0,
            "documents_parsed": 0,
            "documents_failed": 0,
            "relationship_count": 0,
            "operating_observation_count": 0,
            "guidance_statement_count": 0,
        }
        warnings: list[str] = []
        try:
            discovery = self.collector.discover(company, command)
        except Exception as error:
            warnings.append(str(error))
            counts["documents_failed"] += 1
            self.refreshes.add_item(
                refresh_id,
                f"{symbol}:discovery",
                DocumentCollectionStatus.PROVIDER_FAILED,
                reason=f"SEC source discovery failed: {error}",
            )
            coverage = self._coverage(company.company_id, counts, refresh_id, provider_failed=True)
            return self.refreshes.finish(refresh_id, IntelligenceRefreshStatus.FAILED, counts, coverage, warnings)
        counts["documents_discovered"] = len(discovery.documents)
        warnings.extend(discovery.warnings)
        for failure in discovery.failures:
            counts["documents_failed"] += 1
            self.refreshes.add_item(
                refresh_id,
                failure.external_id,
                failure.status,
                source_url=failure.source_url,
                reason=failure.reason,
            )
        if not discovery.documents and not discovery.failures:
            self.refreshes.add_item(
                refresh_id,
                f"{symbol}:no-disclosure",
                DocumentCollectionStatus.NO_DISCLOSURE,
                reason="No supported SEC filing or exhibit was disclosed inside the requested filing window.",
            )
        total = max(len(discovery.documents), 1)
        for index, discovered in enumerate(discovery.documents):
            if cancelled and cancelled():
                warnings.append("The intelligence refresh was cancelled; completed documents remain available.")
                coverage = self._coverage(company.company_id, counts, refresh_id)
                return self.refreshes.finish(refresh_id, IntelligenceRefreshStatus.CANCELLED, counts, coverage, warnings)
            if progress:
                progress(index / total, discovered.external_id)
            latest = self.evidence.latest_document(company.company_id, discovered.source, discovered.external_id)
            content_record = self.evidence.get_content(latest.document_id) if latest else None
            if self._fresh_unchanged(latest, content_record, command.force):
                counts["documents_unchanged"] += 1
                self.refreshes.add_item(
                    refresh_id,
                    discovered.external_id,
                    DocumentCollectionStatus.UNCHANGED,
                    source_url=discovered.source_url,
                    accession_number=discovered.accession_number,
                    form=discovered.form,
                    document_id=latest.document_id,
                    reason="An unchanged parsed SEC archive document is already cached locally.",
                )
                continue
            document = None
            try:
                content = self.collector.download(company, discovered)
                retrieved_at = datetime.now(timezone.utc)
                document = self.evidence.save_document(
                    EvidenceDocumentCreate(
                        company_id=company.company_id,
                        source=discovered.source,
                        dataset=discovered.dataset,
                        document_type=discovered.document_type,
                        external_id=discovered.external_id,
                        title=discovered.title,
                        form=discovered.form,
                        accession_number=discovered.accession_number,
                        source_url=discovered.source_url,
                        filed_at=discovered.filed_at,
                        published_at=discovered.published_at,
                        known_at=discovered.known_at,
                        retrieved_at=retrieved_at,
                        content_hash=sha256(content).hexdigest(),
                        mime_type=discovered.mime_type,
                        source_metadata=discovered.source_metadata,
                        quality_warnings=discovered.quality_warnings,
                    )
                )
                self.evidence.save_content(document.document_id, content, parser_version=DOCUMENT_PARSER_VERSION)
                counts["documents_downloaded"] += 1
                if document.parse_status == EvidenceParseStatus.FAILED:
                    self.evidence.retry_parse(document.document_id)
                parsed = self.parser.parse(content, discovered.mime_type)
            except UnsupportedDocumentFormat as error:
                counts["documents_failed"] += 1
                reason = f"unsupported_format: {error}"
                if document is not None and not self.evidence.list_spans(document.document_id):
                    self.evidence.mark_parse_failed(document.document_id, reason)
                self.refreshes.add_item(
                    refresh_id,
                    discovered.external_id,
                    DocumentCollectionStatus.UNSUPPORTED_FORMAT,
                    source_url=discovered.source_url,
                    accession_number=discovered.accession_number,
                    form=discovered.form,
                    document_id=document.document_id if document else None,
                    reason=str(error),
                )
                continue
            except ProviderUnavailable as error:
                counts["documents_failed"] += 1
                self.refreshes.add_item(
                    refresh_id,
                    discovered.external_id,
                    DocumentCollectionStatus.PROVIDER_FAILED,
                    source_url=discovered.source_url,
                    accession_number=discovered.accession_number,
                    form=discovered.form,
                    reason=str(error),
                )
                continue
            except Exception as error:
                counts["documents_failed"] += 1
                if document is not None and not self.evidence.list_spans(document.document_id):
                    self.evidence.mark_parse_failed(document.document_id, f"parse_failed: {error}")
                self.refreshes.add_item(
                    refresh_id,
                    discovered.external_id,
                    DocumentCollectionStatus.PARSE_FAILED,
                    source_url=discovered.source_url,
                    accession_number=discovered.accession_number,
                    form=discovered.form,
                    document_id=document.document_id if document else None,
                    reason=str(error),
                )
                continue
            try:
                extracted = self.extraction.extract(symbol, company.company_id, document, parsed)
                counts["relationship_count"] += extracted.relationship_count
                counts["operating_observation_count"] += extracted.operating_observation_count
                counts["guidance_statement_count"] += extracted.guidance_statement_count
                warnings.extend(extracted.warnings)
                self.evidence.mark_parsed(document.document_id, parsed.parser_version)
                counts["documents_parsed"] += 1
                self.refreshes.add_item(
                    refresh_id,
                    discovered.external_id,
                    DocumentCollectionStatus.PARSED,
                    source_url=discovered.source_url,
                    accession_number=discovered.accession_number,
                    form=discovered.form,
                    document_id=document.document_id,
                    reason=f"Persisted {extracted.evidence_span_count} inspectable evidence spans.",
                )
            except Exception as error:
                counts["documents_failed"] += 1
                warnings.append(f"Extraction failed for {discovered.external_id}: {error}")
                self.evidence.mark_parsed(document.document_id, parsed.parser_version)
                counts["documents_parsed"] += 1
                self.refreshes.add_item(
                    refresh_id,
                    discovered.external_id,
                    DocumentCollectionStatus.EXTRACTION_FAILED,
                    source_url=discovered.source_url,
                    accession_number=discovered.accession_number,
                    form=discovered.form,
                    document_id=document.document_id,
                    reason=f"The source parsed, but structured extraction failed: {error}",
                )
        if progress:
            progress(1.0, None)
        successful = counts["documents_parsed"] + counts["documents_unchanged"]
        status = (
            IntelligenceRefreshStatus.PARTIAL
            if successful and counts["documents_failed"]
            else IntelligenceRefreshStatus.FAILED
            if counts["documents_failed"] and not successful
            else IntelligenceRefreshStatus.COMPLETED
        )
        coverage = self._coverage(company.company_id, counts, refresh_id)
        return self.refreshes.finish(refresh_id, status, counts, coverage, warnings)

    def health(self, ticker: str) -> IntelligenceSourceHealth:
        symbol = ticker.strip().upper()
        company = self.identities.resolve_ticker(symbol)
        if company is None:
            raise LookupError(f"No canonical company identity exists for ticker {symbol}.")
        latest = self.refreshes.latest(company.company_id)
        document_count = self.evidence.count_documents(company.company_id)
        parsed_count = self.evidence.count_documents_by_status(company.company_id, EvidenceParseStatus.PARSED)
        failed_count = self.evidence.count_documents_by_status(company.company_id, EvidenceParseStatus.FAILED)
        if latest:
            coverage = latest.coverage or self._coverage(company.company_id, {}, latest.refresh_id)
            warnings = latest.warnings
        else:
            coverage = [
                ModuleCoverage(
                    module=module,
                    status=ModuleCoverageStatus.UNAVAILABLE,
                    message="No intelligence source refresh has been run for this company.",
                )
                for module in ("evidence", "network", "operations", "guidance")
            ]
            warnings = ["Run Refresh Intelligence Sources to discover permitted public SEC evidence."]
        return IntelligenceSourceHealth(
            company_id=company.company_id,
            ticker=symbol,
            last_refresh=latest,
            document_count=document_count,
            parsed_document_count=parsed_count,
            failed_document_count=failed_count,
            coverage=coverage,
            warnings=warnings,
        )

    @staticmethod
    def _fresh_unchanged(document, content, force: bool) -> bool:
        if force or document is None or content is None or document.parse_status != EvidenceParseStatus.PARSED:
            return False
        return content.parser_version == DOCUMENT_PARSER_VERSION

    def _coverage(
        self,
        company_id: str,
        counts: dict[str, int],
        refresh_id: str | None = None,
        provider_failed: bool = False,
    ) -> list[ModuleCoverage]:
        parsed_count = self.evidence.count_documents_by_status(company_id, EvidenceParseStatus.PARSED)
        span_count = self.evidence.count_spans(company_id)
        relationship_count = self.relationships.count_company_observations(company_id)
        operating_count = self.operations.count_company_observations(company_id)
        guidance_count = self.guidance.count_company_statements(company_id)
        failures = counts.get("documents_failed", 0)
        statuses = {item.status for item in self.refreshes.items(refresh_id)} if refresh_id else set()

        def missing_status() -> ModuleCoverageStatus:
            if provider_failed or DocumentCollectionStatus.PROVIDER_FAILED in statuses:
                return ModuleCoverageStatus.PROVIDER_FAILED
            if failures and DocumentCollectionStatus.PARSE_FAILED in statuses:
                return ModuleCoverageStatus.PARSER_FAILED
            if failures and DocumentCollectionStatus.EXTRACTION_FAILED in statuses:
                return ModuleCoverageStatus.EXTRACTION_FAILED
            if failures and DocumentCollectionStatus.UNSUPPORTED_FORMAT in statuses:
                return ModuleCoverageStatus.UNSUPPORTED_FORMAT
            return ModuleCoverageStatus.NO_DISCLOSURE

        def coverage(module: str, records: int, spans: int = 0) -> ModuleCoverage:
            if records:
                return ModuleCoverage(
                    module=module,
                    status=ModuleCoverageStatus.POPULATED,
                    record_count=records,
                    evidence_span_count=spans,
                    message=f"{records} source-backed {module} record(s) are available.",
                )
            status = missing_status()
            messages = {
                ModuleCoverageStatus.NO_DISCLOSURE: "No supported public disclosure was found in parsed documents.",
                ModuleCoverageStatus.PARSER_FAILED: "Collection succeeded, but parsing failed before this module could be populated.",
                ModuleCoverageStatus.EXTRACTION_FAILED: "The source parsed, but structured extraction failed for this refresh.",
                ModuleCoverageStatus.PROVIDER_FAILED: "The SEC provider failed before this module could be evaluated.",
                ModuleCoverageStatus.UNSUPPORTED_FORMAT: "Only unsupported source formats were discovered for this module.",
            }
            return ModuleCoverage(module=module, status=status, message=messages[status])

        return [
            coverage("evidence", parsed_count, span_count),
            coverage("network", relationship_count),
            coverage("operations", operating_count),
            coverage("guidance", guidance_count),
        ]
