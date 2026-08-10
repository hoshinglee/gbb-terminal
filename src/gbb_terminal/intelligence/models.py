from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .identity import normalize_cik, normalize_exchange, normalize_fiscal_year_end, normalize_ticker


class CompanyStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class CompanyProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source: str = Field(min_length=1, max_length=120)
    dataset: str = Field(default="company_identity", min_length=1, max_length=120)
    observation_timestamp: datetime
    known_at: datetime
    retrieved_at: datetime
    status: str = Field(default="Observed", min_length=1, max_length=80)
    quality_warnings: list[str] = Field(default_factory=list)
    remaining_quota: int | None = None
    cached: bool = False

    @field_validator("observation_timestamp", "known_at", "retrieved_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Provenance timestamps must include a timezone.")
        return value

    @classmethod
    def local(cls, source: str = "Local Research", warning: str | None = None) -> "CompanyProvenance":
        now = datetime.now(timezone.utc)
        return cls(
            source=source,
            observation_timestamp=now,
            known_at=now,
            retrieved_at=now,
            quality_warnings=[warning] if warning else [],
        )


class CompanyRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cik: str
    legal_name: str = Field(min_length=1, max_length=300)
    primary_ticker: str
    exchange: str | None = Field(default=None, max_length=120)
    sector: str | None = Field(default=None, max_length=160)
    industry: str | None = Field(default=None, max_length=240)
    fiscal_year_end: str | None = None
    effective_from: date = Field(default_factory=date.today)
    provenance: CompanyProvenance

    @field_validator("cik", mode="before")
    @classmethod
    def validate_cik(cls, value: str | int) -> str:
        return normalize_cik(value)

    @field_validator("primary_ticker", mode="before")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        return normalize_ticker(value)

    @field_validator("exchange", mode="before")
    @classmethod
    def validate_exchange(cls, value: str | None) -> str | None:
        return normalize_exchange(value)

    @field_validator("fiscal_year_end", mode="before")
    @classmethod
    def validate_fiscal_year_end(cls, value: str | None) -> str | None:
        return normalize_fiscal_year_end(value)


class SecurityMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    security_id: str
    company_id: str
    ticker: str
    exchange: str | None = None
    valid_from: date
    valid_to: date | None = None
    is_primary: bool
    status: CompanyStatus
    provenance: CompanyProvenance
    created_at: datetime
    updated_at: datetime


class CompanyIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_id: str
    cik: str
    legal_name: str
    primary_ticker: str | None = None
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    fiscal_year_end: str | None = None
    status: CompanyStatus
    provenance: CompanyProvenance
    securities: list[SecurityMapping] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
