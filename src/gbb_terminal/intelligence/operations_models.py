from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .evidence_models import EvidenceClaimLink, EvidenceDocument, EvidenceSpan
from .models import CompanyIdentity


OPERATIONS_MODEL_VERSION = "1.0.0"


class OperatingMetricCategory(StrEnum):
    SEGMENT = "segment"
    GEOGRAPHY = "geography"
    KPI = "kpi"


class OperatingValueType(StrEnum):
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    COUNT = "count"
    RATIO = "ratio"
    DURATION = "duration"
    OTHER = "other"


class OperatingMetricDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_id: str = Field(min_length=1, max_length=120)
    category: OperatingMetricCategory
    definition_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z][a-z0-9_.-]*$")
    label: str = Field(min_length=1, max_length=300)
    measure: str = Field(min_length=1, max_length=160, pattern=r"^[a-z][a-z0-9_.-]*$")
    unit: str = Field(min_length=1, max_length=80)
    value_type: OperatingValueType
    reporting_basis: str = Field(min_length=1, max_length=200)
    valid_from: date | None = None
    valid_to: date | None = None
    supersedes_definition_id: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    known_at: datetime
    extraction_method: str = Field(min_length=1, max_length=160)
    evidence_span_ids: list[str] = Field(min_length=1, max_length=50)

    @field_validator("known_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Operating metric definition known_at must include a timezone.")
        return value

    @field_validator("evidence_span_ids")
    @classmethod
    def deduplicate_evidence(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_dates(self) -> "OperatingMetricDefinitionCreate":
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("Operating metric definition valid_to cannot precede valid_from.")
        return self


class OperatingMetricDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition_id: str
    company_id: str
    category: OperatingMetricCategory
    definition_key: str
    label: str
    measure: str
    unit: str
    value_type: OperatingValueType
    reporting_basis: str
    version: int = Field(ge=1)
    valid_from: date | None = None
    valid_to: date | None = None
    supersedes_definition_id: str | None = None
    description: str | None = None
    known_at: datetime
    extraction_method: str
    model_version: str = OPERATIONS_MODEL_VERSION
    created_at: datetime


class OperatingMetricObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    definition_id: str = Field(min_length=1, max_length=120)
    period_start: date | None = None
    period_end: date
    fiscal_year: int | None = Field(default=None, ge=1900, le=2300)
    fiscal_period: str | None = Field(default=None, max_length=40)
    value: float
    unit: str = Field(min_length=1, max_length=80)
    known_at: datetime
    extraction_method: str = Field(min_length=1, max_length=160)
    evidence_span_ids: list[str] = Field(min_length=1, max_length=50)

    @field_validator("known_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Operating metric observation known_at must include a timezone.")
        return value

    @field_validator("evidence_span_ids")
    @classmethod
    def deduplicate_evidence(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_period(self) -> "OperatingMetricObservationCreate":
        if self.period_start and self.period_end < self.period_start:
            raise ValueError("Operating metric period_end cannot precede period_start.")
        return self


class OperatingMetricObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    definition_id: str
    period_start: date | None = None
    period_end: date
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    value: float
    unit: str
    known_at: datetime
    extraction_method: str
    created_at: datetime


class OperatingMetricEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link: EvidenceClaimLink
    document: EvidenceDocument
    span: EvidenceSpan


class OperatingMetricPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation: OperatingMetricObservation
    mix_percent: float | None = None
    growth_percent: float | None = None
    evidence: list[OperatingMetricEvidence]


class OperatingMetricSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition: OperatingMetricDefinition
    definition_evidence: list[OperatingMetricEvidence]
    points: list[OperatingMetricPoint]


class OperatingDefinitionTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prior_definition_id: str
    next_definition_id: str
    definition_key: str
    prior_label: str
    next_label: str
    prior_reporting_basis: str
    next_reporting_basis: str
    known_at: datetime


class OperatingIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: CompanyIdentity
    as_of: datetime
    series: list[OperatingMetricSeries]
    transitions: list[OperatingDefinitionTransition]
    warnings: list[str] = Field(default_factory=list)


class OperatingIntelligenceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: list[OperatingMetricCategory] = Field(default_factory=list, max_length=3)
    as_of: datetime | None = None

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Operating intelligence as_of must include a timezone.")
        return value
