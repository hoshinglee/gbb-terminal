from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .evidence_models import EvidenceDocumentType


COLLECTION_MODEL_VERSION = "1.0.0"


class IntelligenceRefreshStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DocumentCollectionStatus(StrEnum):
    DISCOVERED = "discovered"
    UNCHANGED = "unchanged"
    DOWNLOADED = "downloaded"
    PARSED = "parsed"
    NO_DISCLOSURE = "no_disclosure"
    PARSE_FAILED = "parse_failed"
    EXTRACTION_FAILED = "extraction_failed"
    PROVIDER_FAILED = "provider_failed"
    UNSUPPORTED_FORMAT = "unsupported_format"


class ModuleCoverageStatus(StrEnum):
    POPULATED = "populated"
    NO_DISCLOSURE = "no_disclosure"
    PARSER_FAILED = "parser_failed"
    EXTRACTION_FAILED = "extraction_failed"
    PROVIDER_FAILED = "provider_failed"
    UNSUPPORTED_FORMAT = "unsupported_format"
    UNAVAILABLE = "unavailable"


class IntelligenceRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forms: list[str] = Field(
        default_factory=lambda: ["10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "6-K", "20-F"],
        min_length=1,
        max_length=20,
    )
    max_filings: int = Field(default=24, ge=1, le=200)
    include_exhibits: bool = True
    force: bool = False

    @field_validator("forms")
    @classmethod
    def normalize_forms(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip().upper() for value in values if value.strip()))


class DiscoveredEvidenceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    source: str
    dataset: str
    document_type: EvidenceDocumentType
    external_id: str
    title: str | None = None
    form: str | None = None
    accession_number: str | None = None
    source_url: str
    filed_at: datetime | None = None
    published_at: datetime | None = None
    known_at: datetime
    mime_type: str
    source_metadata: dict = Field(default_factory=dict)
    quality_warnings: list[str] = Field(default_factory=list)
    prefetched_content: bytes | None = Field(default=None, exclude=True)

    @field_validator("filed_at", "published_at", "known_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Discovered evidence timestamps must include a timezone.")
        return value


class CollectionFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str
    source_url: str | None = None
    status: DocumentCollectionStatus
    reason: str


class CollectorDiscovery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[DiscoveredEvidenceDocument] = Field(default_factory=list)
    failures: list[CollectionFailure] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class IntelligenceRefreshItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    refresh_id: str
    external_id: str
    source_url: str | None = None
    accession_number: str | None = None
    form: str | None = None
    status: DocumentCollectionStatus
    document_id: str | None = None
    reason: str | None = None
    created_at: datetime


class ModuleCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: str
    status: ModuleCoverageStatus
    record_count: int = Field(default=0, ge=0)
    evidence_span_count: int = Field(default=0, ge=0)
    message: str


class IntelligenceRefreshSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_id: str
    company_id: str
    ticker: str
    status: IntelligenceRefreshStatus
    started_at: datetime
    completed_at: datetime | None = None
    documents_discovered: int = Field(default=0, ge=0)
    documents_downloaded: int = Field(default=0, ge=0)
    documents_unchanged: int = Field(default=0, ge=0)
    documents_parsed: int = Field(default=0, ge=0)
    documents_failed: int = Field(default=0, ge=0)
    relationship_count: int = Field(default=0, ge=0)
    operating_observation_count: int = Field(default=0, ge=0)
    guidance_statement_count: int = Field(default=0, ge=0)
    coverage: list[ModuleCoverage] = Field(default_factory=list)
    items: list[IntelligenceRefreshItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    model_version: str = COLLECTION_MODEL_VERSION


class IntelligenceSourceHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    ticker: str
    last_refresh: IntelligenceRefreshSummary | None = None
    document_count: int = Field(default=0, ge=0)
    parsed_document_count: int = Field(default=0, ge=0)
    failed_document_count: int = Field(default=0, ge=0)
    coverage: list[ModuleCoverage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
