from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .identity import normalize_cik
from .models import CompanyProvenance


class FinancialFact(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fact_id: str
    company_id: str
    cik: str
    taxonomy: str
    concept: str
    label: str | None = None
    description: str | None = None
    value: float
    raw_value: str
    unit: str
    period_start: date | None = None
    period_end: date
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    form: str
    filed_date: date
    accepted_at: datetime | None = None
    known_at_source: str
    accession_number: str
    frame: str | None = None
    provenance: CompanyProvenance
    source_metadata: dict = Field(default_factory=dict)

    @field_validator("cik", mode="before")
    @classmethod
    def validate_cik(cls, value: str | int) -> str:
        return normalize_cik(value)

    @field_validator("accepted_at")
    @classmethod
    def require_acceptance_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Acceptance timestamps must include a timezone.")
        return value


class FinancialFactQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concepts: list[str] = Field(default_factory=list, max_length=100)
    forms: list[str] = Field(default_factory=list, max_length=20)
    as_of: datetime | None = None

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("As-of timestamps must include a timezone.")
        return value
