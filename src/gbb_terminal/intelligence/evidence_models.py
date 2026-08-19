from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EVIDENCE_MODEL_VERSION = "1.0.0"


class EvidenceDocumentType(StrEnum):
    FORM_10_K = "10-k"
    FORM_10_Q = "10-q"
    FORM_8_K = "8-k"
    EARNINGS_RELEASE = "earnings_release"
    ANNUAL_REPORT = "annual_report"
    INVESTOR_PRESENTATION = "investor_presentation"
    OTHER = "other"


class EvidenceParseStatus(StrEnum):
    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"


class EvidenceRole(StrEnum):
    SUPPORT = "support"
    CONTEXT = "context"
    CONTRADICTION = "contradiction"


class EvidenceDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_id: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=120)
    dataset: str = Field(min_length=1, max_length=160)
    document_type: EvidenceDocumentType
    external_id: str = Field(min_length=1, max_length=300)
    title: str | None = Field(default=None, max_length=500)
    form: str | None = Field(default=None, max_length=40)
    accession_number: str | None = Field(default=None, max_length=80)
    source_url: str = Field(min_length=1, max_length=2000)
    filed_at: datetime | None = None
    published_at: datetime | None = None
    known_at: datetime
    retrieved_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    mime_type: str = Field(default="text/html", min_length=1, max_length=120)
    source_metadata: dict = Field(default_factory=dict)
    quality_warnings: list[str] = Field(default_factory=list)

    @field_validator("filed_at", "published_at", "known_at", "retrieved_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Evidence timestamps must include a timezone.")
        return value

    @field_validator("content_hash")
    @classmethod
    def normalize_content_hash(cls, value: str) -> str:
        return value.lower()

    @model_validator(mode="after")
    def validate_availability_timestamps(self) -> "EvidenceDocumentCreate":
        if self.filed_at is None and self.published_at is None:
            raise ValueError("An evidence document requires filed_at or published_at.")
        first_public_timestamp = min(
            timestamp for timestamp in (self.filed_at, self.published_at) if timestamp is not None
        )
        if self.known_at < first_public_timestamp:
            raise ValueError("Evidence known_at cannot precede its filed or published timestamp.")
        if self.retrieved_at < self.known_at:
            raise ValueError("Evidence retrieved_at cannot precede known_at.")
        return self


class EvidenceDocument(EvidenceDocumentCreate):
    document_id: str
    version: int = Field(ge=1)
    supersedes_document_id: str | None = None
    parse_status: EvidenceParseStatus
    parse_error: str | None = None
    model_version: str = EVIDENCE_MODEL_VERSION
    created_at: datetime
    updated_at: datetime


class EvidenceDocumentContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    content: bytes
    encoding: str | None = None
    parser_version: str | None = None
    stored_at: datetime
    parsed_at: datetime | None = None


class EvidenceSpanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_id: str = Field(min_length=1, max_length=120)
    exact_text: str = Field(min_length=1, max_length=20_000)
    section: str | None = Field(default=None, max_length=500)
    page_number: int | None = Field(default=None, ge=1)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=1)
    context_before: str | None = Field(default=None, max_length=5_000)
    context_after: str | None = Field(default=None, max_length=5_000)
    extraction_method: str = Field(min_length=1, max_length=120)
    extracted_at: datetime
    source_metadata: dict = Field(default_factory=dict)

    @field_validator("extracted_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Evidence extraction timestamps must include a timezone.")
        return value

    @model_validator(mode="after")
    def validate_offsets(self) -> "EvidenceSpanCreate":
        if (self.start_offset is None) != (self.end_offset is None):
            raise ValueError("Evidence span offsets must be supplied together.")
        if self.start_offset is not None and self.end_offset is not None and self.end_offset <= self.start_offset:
            raise ValueError("Evidence span end_offset must be greater than start_offset.")
        return self


class EvidenceSpan(EvidenceSpanCreate):
    span_id: str
    span_hash: str
    created_at: datetime


class EvidenceClaimLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    claim_type: str = Field(min_length=1, max_length=120, pattern=r"^[a-z][a-z0-9_.-]*$")
    claim_id: str = Field(min_length=1, max_length=240)
    span_id: str = Field(min_length=1, max_length=120)
    role: EvidenceRole = EvidenceRole.SUPPORT


class EvidenceClaimLink(EvidenceClaimLinkCreate):
    created_at: datetime


class EvidenceClaimSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link: EvidenceClaimLink
    span: EvidenceSpan


class EvidenceDocumentQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_types: list[EvidenceDocumentType] = Field(default_factory=list, max_length=20)
    as_of: datetime | None = None
    limit: int = Field(default=100, ge=1, le=500)

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Evidence as_of must include a timezone.")
        return value
