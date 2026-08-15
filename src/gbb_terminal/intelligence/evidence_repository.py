from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256

import duckdb

from .evidence_models import (
    EVIDENCE_MODEL_VERSION,
    EvidenceClaimLink,
    EvidenceClaimLinkCreate,
    EvidenceClaimSpan,
    EvidenceDocument,
    EvidenceDocumentCreate,
    EvidenceDocumentQuery,
    EvidenceParseStatus,
    EvidenceSpan,
    EvidenceSpanCreate,
)


DOCUMENT_COLUMNS = """document_id, company_id, source, dataset, document_type, external_id, version,
    supersedes_document_id, title, form, accession_number, source_url, filed_at, published_at, known_at,
    retrieved_at, content_hash, mime_type, parse_status, parse_error, source_metadata, quality_warnings,
    model_version, created_at, updated_at"""

SPAN_COLUMNS = """span_id, document_id, span_hash, exact_text, section, page_number, start_offset, end_offset,
    context_before, context_after, extraction_method, extracted_at, source_metadata, created_at"""


class EvidenceRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def save_document(self, document: EvidenceDocumentCreate) -> EvidenceDocument:
        self._require_company(document.company_id)
        existing = self.connection.execute(
            """SELECT document_id FROM evidence_documents
               WHERE company_id = ? AND source = ? AND external_id = ? AND content_hash = ?""",
            [document.company_id, document.source, document.external_id, document.content_hash],
        ).fetchone()
        if existing:
            return self._require_document(existing[0])

        latest = self.connection.execute(
            """SELECT document_id, version FROM evidence_documents
               WHERE company_id = ? AND source = ? AND external_id = ?
               ORDER BY version DESC LIMIT 1""",
            [document.company_id, document.source, document.external_id],
        ).fetchone()
        version = int(latest[1]) + 1 if latest else 1
        supersedes_document_id = latest[0] if latest else None
        document_id = sha256(
            f"{document.company_id}\0{document.source}\0{document.external_id}\0{document.content_hash}".encode()
        ).hexdigest()
        now = self._utc_now()
        self.connection.execute(
            """INSERT INTO evidence_documents
               (document_id, company_id, source, dataset, document_type, external_id, version,
                supersedes_document_id, title, form, accession_number, source_url, filed_at, published_at,
                known_at, retrieved_at, content_hash, mime_type, parse_status, parse_error, source_metadata,
                quality_warnings, model_version, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, ?, ?, ?, ?, ?)""",
            [
                document_id,
                document.company_id,
                document.source,
                document.dataset,
                document.document_type.value,
                document.external_id,
                version,
                supersedes_document_id,
                document.title,
                document.form.upper() if document.form else None,
                document.accession_number,
                document.source_url,
                self._naive_utc(document.filed_at),
                self._naive_utc(document.published_at),
                self._naive_utc(document.known_at),
                self._naive_utc(document.retrieved_at),
                document.content_hash,
                document.mime_type,
                json.dumps(document.source_metadata),
                json.dumps(document.quality_warnings),
                EVIDENCE_MODEL_VERSION,
                now,
                now,
            ],
        )
        return self._require_document(document_id)

    def get_document(self, document_id: str) -> EvidenceDocument | None:
        row = self.connection.execute(
            f"SELECT {DOCUMENT_COLUMNS} FROM evidence_documents WHERE document_id = ?",
            [document_id],
        ).fetchone()
        return self._row_to_document(row) if row else None

    def list_documents(self, company_id: str, query: EvidenceDocumentQuery | None = None) -> list[EvidenceDocument]:
        request = query or EvidenceDocumentQuery()
        conditions, parameters = self._document_filters(company_id, request)
        parameters.append(request.limit)
        rows = self.connection.execute(
            f"""SELECT {DOCUMENT_COLUMNS} FROM evidence_documents
                WHERE {' AND '.join(conditions)}
                ORDER BY known_at DESC, source, external_id, version DESC
                LIMIT ?""",
            parameters,
        ).fetchall()
        return [self._row_to_document(row) for row in rows]

    def count_documents(self, company_id: str, query: EvidenceDocumentQuery | None = None) -> int:
        request = query or EvidenceDocumentQuery()
        conditions, parameters = self._document_filters(company_id, request)
        return int(
            self.connection.execute(
                f"SELECT count(*) FROM evidence_documents WHERE {' AND '.join(conditions)}",
                parameters,
            ).fetchone()[0]
        )

    def save_span(self, span: EvidenceSpanCreate) -> EvidenceSpan:
        document = self._require_document(span.document_id)
        if document.parse_status == EvidenceParseStatus.FAILED:
            raise ValueError("Evidence spans cannot be added to a document with failed parsing.")
        if span.extracted_at < document.retrieved_at:
            raise ValueError("Evidence span extracted_at cannot precede document retrieval.")

        span_hash = sha256(
            json.dumps(
                {
                    "exact_text": span.exact_text,
                    "section": span.section,
                    "page_number": span.page_number,
                    "start_offset": span.start_offset,
                    "end_offset": span.end_offset,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        span_id = sha256(f"{span.document_id}:{span_hash}".encode()).hexdigest()
        now = self._utc_now()
        self.connection.execute(
            """INSERT OR IGNORE INTO evidence_spans
               (span_id, document_id, span_hash, exact_text, section, page_number, start_offset, end_offset,
                context_before, context_after, extraction_method, extracted_at, source_metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                span_id,
                span.document_id,
                span_hash,
                span.exact_text,
                span.section,
                span.page_number,
                span.start_offset,
                span.end_offset,
                span.context_before,
                span.context_after,
                span.extraction_method,
                self._naive_utc(span.extracted_at),
                json.dumps(span.source_metadata),
                now,
            ],
        )
        self.connection.execute(
            """UPDATE evidence_documents
               SET parse_status = 'parsed', parse_error = NULL, updated_at = ?
               WHERE document_id = ? AND parse_status = 'pending'""",
            [now, span.document_id],
        )
        return self._require_span(span_id)

    def get_span(self, span_id: str) -> EvidenceSpan | None:
        row = self.connection.execute(
            f"SELECT {SPAN_COLUMNS} FROM evidence_spans WHERE span_id = ?",
            [span_id],
        ).fetchone()
        return self._row_to_span(row) if row else None

    def list_spans(self, document_id: str) -> list[EvidenceSpan]:
        rows = self.connection.execute(
            f"""SELECT {SPAN_COLUMNS} FROM evidence_spans
                WHERE document_id = ?
                ORDER BY page_number NULLS LAST, start_offset NULLS LAST, created_at""",
            [document_id],
        ).fetchall()
        return [self._row_to_span(row) for row in rows]

    def mark_parse_failed(self, document_id: str, error: str) -> EvidenceDocument:
        self._require_document(document_id)
        if self.connection.execute(
            "SELECT count(*) FROM evidence_spans WHERE document_id = ?",
            [document_id],
        ).fetchone()[0]:
            raise ValueError("A document with persisted evidence spans cannot be marked as failed.")
        self.connection.execute(
            """UPDATE evidence_documents
               SET parse_status = 'failed', parse_error = ?, updated_at = ?
               WHERE document_id = ?""",
            [error.strip()[:2000], self._utc_now(), document_id],
        )
        return self._require_document(document_id)

    def link_claim(self, link: EvidenceClaimLinkCreate) -> EvidenceClaimLink:
        self._require_span(link.span_id)
        now = self._utc_now()
        self.connection.execute(
            """INSERT OR IGNORE INTO evidence_claim_links
               (claim_type, claim_id, span_id, evidence_role, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [link.claim_type, link.claim_id, link.span_id, link.role.value, now],
        )
        row = self.connection.execute(
            """SELECT claim_type, claim_id, span_id, evidence_role, created_at
               FROM evidence_claim_links
               WHERE claim_type = ? AND claim_id = ? AND span_id = ? AND evidence_role = ?""",
            [link.claim_type, link.claim_id, link.span_id, link.role.value],
        ).fetchone()
        return EvidenceClaimLink(
            claim_type=row[0],
            claim_id=row[1],
            span_id=row[2],
            role=row[3],
            created_at=self._aware_utc(row[4]),
        )

    def list_claim_spans(
        self,
        company_id: str,
        claim_type: str,
        claim_id: str,
        as_of: datetime | None = None,
    ) -> list[EvidenceClaimSpan]:
        conditions = ["d.company_id = ?", "l.claim_type = ?", "l.claim_id = ?"]
        parameters: list[object] = [company_id, claim_type, claim_id]
        if as_of is not None:
            conditions.append("d.known_at <= ?")
            parameters.append(self._naive_utc(as_of))
        qualified_span_columns = ", ".join(f"s.{column.strip()}" for column in SPAN_COLUMNS.split(","))
        rows = self.connection.execute(
            f"""SELECT {qualified_span_columns}, l.claim_type, l.claim_id, l.evidence_role, l.created_at
                FROM evidence_claim_links l
                JOIN evidence_spans s ON s.span_id = l.span_id
                JOIN evidence_documents d ON d.document_id = s.document_id
                WHERE {' AND '.join(conditions)}
                ORDER BY d.known_at, s.page_number NULLS LAST, s.start_offset NULLS LAST""",
            parameters,
        ).fetchall()
        span_column_count = len(SPAN_COLUMNS.split(","))
        return [
            EvidenceClaimSpan(
                link=EvidenceClaimLink(
                    claim_type=row[span_column_count],
                    claim_id=row[span_column_count + 1],
                    span_id=row[0],
                    role=row[span_column_count + 2],
                    created_at=self._aware_utc(row[span_column_count + 3]),
                ),
                span=self._row_to_span(row[:span_column_count]),
            )
            for row in rows
        ]

    @staticmethod
    def _document_filters(
        company_id: str,
        query: EvidenceDocumentQuery,
    ) -> tuple[list[str], list[object]]:
        conditions = ["company_id = ?"]
        parameters: list[object] = [company_id]
        if query.document_types:
            conditions.append(f"document_type IN ({','.join('?' for _ in query.document_types)})")
            parameters.extend(document_type.value for document_type in query.document_types)
        if query.as_of is not None:
            conditions.append("known_at <= ?")
            parameters.append(EvidenceRepository._naive_utc(query.as_of))
        return conditions, parameters

    def _require_company(self, company_id: str) -> None:
        if self.connection.execute("SELECT 1 FROM companies WHERE company_id = ?", [company_id]).fetchone() is None:
            raise LookupError(f"No canonical company exists for company_id {company_id}.")

    def _require_document(self, document_id: str) -> EvidenceDocument:
        document = self.get_document(document_id)
        if document is None:
            raise LookupError(f"No evidence document exists for document_id {document_id}.")
        return document

    def _require_span(self, span_id: str) -> EvidenceSpan:
        span = self.get_span(span_id)
        if span is None:
            raise LookupError(f"No evidence span exists for span_id {span_id}.")
        return span

    @staticmethod
    def _row_to_document(row: tuple) -> EvidenceDocument:
        return EvidenceDocument(
            document_id=row[0],
            company_id=row[1],
            source=row[2],
            dataset=row[3],
            document_type=row[4],
            external_id=row[5],
            version=row[6],
            supersedes_document_id=row[7],
            title=row[8],
            form=row[9],
            accession_number=row[10],
            source_url=row[11],
            filed_at=EvidenceRepository._aware_utc(row[12]),
            published_at=EvidenceRepository._aware_utc(row[13]),
            known_at=EvidenceRepository._aware_utc(row[14]),
            retrieved_at=EvidenceRepository._aware_utc(row[15]),
            content_hash=row[16],
            mime_type=row[17],
            parse_status=row[18],
            parse_error=row[19],
            source_metadata=json.loads(row[20]),
            quality_warnings=json.loads(row[21]),
            model_version=row[22],
            created_at=EvidenceRepository._aware_utc(row[23]),
            updated_at=EvidenceRepository._aware_utc(row[24]),
        )

    @staticmethod
    def _row_to_span(row: tuple) -> EvidenceSpan:
        return EvidenceSpan(
            span_id=row[0],
            document_id=row[1],
            span_hash=row[2],
            exact_text=row[3],
            section=row[4],
            page_number=row[5],
            start_offset=row[6],
            end_offset=row[7],
            context_before=row[8],
            context_after=row[9],
            extraction_method=row[10],
            extracted_at=EvidenceRepository._aware_utc(row[11]),
            source_metadata=json.loads(row[12]),
            created_at=EvidenceRepository._aware_utc(row[13]),
        )

    @staticmethod
    def _naive_utc(value: datetime | None) -> datetime | None:
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value is not None else None

    @staticmethod
    def _aware_utc(value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None else None

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)
