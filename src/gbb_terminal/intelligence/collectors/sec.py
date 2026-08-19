from __future__ import annotations

from datetime import date, datetime, time, timezone
from html.parser import HTMLParser
from pathlib import PurePosixPath

from ...market_data.providers.base import ProviderUnavailable
from ...market_data.providers.sec import SECProvider
from ..collection_models import (
    CollectionFailure,
    CollectorDiscovery,
    DiscoveredEvidenceDocument,
    DocumentCollectionStatus,
    IntelligenceRefreshRequest,
)
from ..evidence_models import EvidenceDocumentType
from ..models import CompanyIdentity
from .base import EvidenceCollector


SUPPORTED_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "8-K/A", "6-K", "6-K/A", "20-F", "20-F/A"}
EXHIBIT_TYPES = {"EX-99", "EX-99.1", "EX-99.2", "EX-99.3"}


class FilingIndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._link: str | None = None
        self._row_link: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        if normalized == "tr":
            self._row = []
            self._row_link = None
        elif normalized in {"td", "th"} and self._row is not None:
            self._cell = []
        elif normalized == "a" and self._cell is not None:
            self._link = dict(attrs).get("href")

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            if self._link:
                self._row_link = self._link
            self._cell = None
            self._link = None
        elif normalized == "tr" and self._row is not None:
            if len(self._row) >= 4 and self._row[0].casefold() != "seq":
                cells = [*self._row, "", ""]
                self.rows.append(
                    {
                        "sequence": cells[0],
                        "description": cells[1],
                        "document": cells[2],
                        "type": cells[3].upper(),
                        "size": cells[4],
                        "href": self._row_link or "",
                    }
                )
            self._row = None
            self._row_link = None


class SECArchiveCollector(EvidenceCollector):
    name = "SEC EDGAR Archive"

    def __init__(self, provider: SECProvider) -> None:
        self.provider = provider

    def discover(self, company: CompanyIdentity, request: IntelligenceRefreshRequest) -> CollectorDiscovery:
        requested_forms = set(request.forms) & SUPPORTED_FORMS
        if not requested_forms:
            raise ValueError("The refresh request does not contain a supported SEC filing form.")
        envelope = self.provider.submissions(company.cik)
        rows = self._submission_rows(
            envelope.data,
            requested_forms,
            request.max_filings,
            include_exhibits=request.include_exhibits,
        )
        documents: list[DiscoveredEvidenceDocument] = []
        failures: list[CollectionFailure] = []
        warnings = list(envelope.quality_warnings)
        for row in rows:
            accession = row["accessionNumber"]
            primary_document = row.get("primaryDocument") or ""
            if not primary_document:
                failures.append(
                    CollectionFailure(
                        external_id=f"{accession}:primary",
                        status=DocumentCollectionStatus.UNSUPPORTED_FORMAT,
                        reason="SEC submission metadata does not identify a primary document.",
                    )
                )
                continue
            accepted_at = self._accepted_at(row)
            filed_at = self._filed_at(row.get("filingDate"), accepted_at)
            base_url = self.provider._filing_base(company.cik, accession)[1]
            index_url = f"{base_url}/{accession}-index.htm"
            index_content = None
            index_rows: list[dict[str, str]] = []
            try:
                index_content = self.provider.filing_index_page(company.cik, accession)
                parser = FilingIndexParser()
                parser.feed(index_content.decode("utf-8", errors="replace"))
                index_rows = parser.rows
                documents.append(
                    DiscoveredEvidenceDocument(
                        source=self.provider.name,
                        dataset="sec_filing_index",
                        document_type=EvidenceDocumentType.OTHER,
                        external_id=f"{accession}:index",
                        title=f"{row['form']} filing index",
                        form=row["form"],
                        accession_number=accession,
                        source_url=index_url,
                        filed_at=filed_at,
                        published_at=accepted_at,
                        known_at=accepted_at,
                        mime_type="text/html",
                        source_metadata={"items": row.get("items") or None, "report_date": row.get("reportDate") or None},
                        prefetched_content=index_content,
                    )
                )
            except (ProviderUnavailable, ValueError) as error:
                failures.append(
                    CollectionFailure(
                        external_id=f"{accession}:index",
                        source_url=index_url,
                        status=DocumentCollectionStatus.PROVIDER_FAILED,
                        reason=str(error),
                    )
                )
                warnings.append(f"The filing index for {accession} could not be loaded; the primary filing remains discoverable.")

            primary_row = next(
                (item for item in index_rows if PurePosixPath(item["document"]).name == primary_document),
                {},
            )
            documents.append(
                self._document(
                    row,
                    primary_document,
                    self._primary_type(row["form"]),
                    primary_row.get("description") or row.get("primaryDocDescription") or f"{row['form']} filing",
                    primary_row,
                    accepted_at,
                    filed_at,
                    base_url,
                )
            )
            if request.include_exhibits and row["form"].removesuffix("/A") in {"8-K", "6-K"}:
                for item in index_rows:
                    exhibit_type = item.get("type", "").upper()
                    if not any(exhibit_type == candidate or exhibit_type.startswith(f"{candidate}.") for candidate in EXHIBIT_TYPES):
                        continue
                    filename = PurePosixPath(item.get("document", "")).name
                    if not filename or filename == primary_document:
                        continue
                    description = item.get("description") or exhibit_type
                    documents.append(
                        self._document(
                            row,
                            filename,
                            self._exhibit_type(description, filename),
                            description,
                            item,
                            accepted_at,
                            filed_at,
                            base_url,
                        )
                    )
        unique = {document.external_id: document for document in documents}
        if not rows:
            warnings.append("No supported SEC filings were disclosed inside the requested filing limit.")
        return CollectorDiscovery(documents=list(unique.values()), failures=failures, warnings=list(dict.fromkeys(warnings)))

    def download(self, company: CompanyIdentity, document: DiscoveredEvidenceDocument) -> bytes:
        if document.prefetched_content is not None:
            return document.prefetched_content
        filename = document.source_metadata.get("archive_document")
        if not document.accession_number or not filename:
            raise ValueError("The SEC document discovery record is missing its accession or archive file name.")
        return self.provider.filing_document(company.cik, document.accession_number, str(filename))

    def _submission_rows(
        self,
        payload: dict,
        forms: set[str],
        limit: int,
        *,
        include_exhibits: bool,
    ) -> list[dict]:
        rows = SECProvider.filing_rows(payload.get("filings", {}).get("recent", {}))
        for history in payload.get("filings", {}).get("files", []):
            if len([row for row in rows if row.get("form") in forms]) >= limit:
                break
            name = history.get("name")
            if not name:
                continue
            try:
                rows.extend(SECProvider.filing_rows(self.provider.submission_file(name).data))
            except ProviderUnavailable:
                continue
        filtered = [row for row in rows if row.get("form") in forms]
        filtered.sort(key=lambda row: (row.get("acceptanceDateTime") or row.get("filingDate") or ""), reverse=True)
        current_report_forms = {form.removesuffix("/A") for form in forms}
        if include_exhibits and current_report_forms and current_report_forms <= {"8-K", "6-K"}:
            relevant = [row for row in filtered if self._is_relevant_current_report(row)]
            if relevant:
                relevant_accessions = {row.get("accessionNumber") for row in relevant}
                filtered = [*relevant, *(row for row in filtered if row.get("accessionNumber") not in relevant_accessions)]
        return filtered[:limit]

    @staticmethod
    def _is_relevant_current_report(row: dict) -> bool:
        if str(row.get("form", "")).removesuffix("/A") == "6-K":
            return True
        items = {item.strip() for item in str(row.get("items", "")).split(",") if item.strip()}
        return bool(items & {"2.02", "7.01", "8.01"})

    @staticmethod
    def _accepted_at(row: dict) -> datetime:
        raw = row.get("acceptanceDateTime")
        if raw:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        filing_date = date.fromisoformat(row["filingDate"])
        return datetime.combine(filing_date, time(23, 59, 59), tzinfo=timezone.utc)

    @staticmethod
    def _filed_at(raw: str | None, fallback: datetime) -> datetime:
        return datetime.combine(date.fromisoformat(raw), time.min, tzinfo=timezone.utc) if raw else fallback

    @staticmethod
    def _primary_type(form: str) -> EvidenceDocumentType:
        base = form.removesuffix("/A")
        if base == "10-K":
            return EvidenceDocumentType.FORM_10_K
        if base == "10-Q":
            return EvidenceDocumentType.FORM_10_Q
        if base == "8-K":
            return EvidenceDocumentType.FORM_8_K
        if base == "20-F":
            return EvidenceDocumentType.ANNUAL_REPORT
        return EvidenceDocumentType.OTHER

    @staticmethod
    def _exhibit_type(description: str, filename: str) -> EvidenceDocumentType:
        normalized = f"{description} {filename}".casefold()
        return (
            EvidenceDocumentType.INVESTOR_PRESENTATION
            if "presentation" in normalized or "slides" in normalized
            else EvidenceDocumentType.EARNINGS_RELEASE
        )

    @staticmethod
    def _mime_type(filename: str) -> str:
        suffix = PurePosixPath(filename).suffix.casefold()
        return {
            ".htm": "text/html",
            ".html": "text/html",
            ".xhtml": "application/xhtml+xml",
            ".xml": "application/xml",
            ".txt": "text/plain",
            ".pdf": "application/pdf",
        }.get(suffix, "application/octet-stream")

    def _document(
        self,
        filing: dict,
        filename: str,
        document_type: EvidenceDocumentType,
        title: str,
        index_row: dict,
        accepted_at: datetime,
        filed_at: datetime,
        base_url: str,
    ) -> DiscoveredEvidenceDocument:
        accession = filing["accessionNumber"]
        return DiscoveredEvidenceDocument(
            source=self.provider.name,
            dataset="sec_filing_document",
            document_type=document_type,
            external_id=f"{accession}:{filename}",
            title=title,
            form=filing["form"],
            accession_number=accession,
            source_url=f"{base_url}/{filename}",
            filed_at=filed_at,
            published_at=accepted_at,
            known_at=accepted_at,
            mime_type=self._mime_type(filename),
            source_metadata={
                "archive_document": filename,
                "archive_size": index_row.get("size") or None,
                "archive_sequence": index_row.get("sequence") or None,
                "archive_type": index_row.get("type") or filing["form"],
                "report_date": filing.get("reportDate") or None,
                "items": filing.get("items") or None,
            },
        )
