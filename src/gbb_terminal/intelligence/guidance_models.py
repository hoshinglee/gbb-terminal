from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .evidence_models import EvidenceClaimLink, EvidenceDocument, EvidenceSpan
from .models import CompanyIdentity


GUIDANCE_MODEL_VERSION = "1.0.0"


class GuidanceStatementType(StrEnum):
    FINANCIAL_GUIDANCE = "financial_guidance"
    STRATEGIC_COMMITMENT = "strategic_commitment"
    KPI_TARGET = "kpi_target"
    RISK_CONSTRAINT = "risk_constraint"


class GuidanceValueKind(StrEnum):
    NUMERIC_RANGE = "numeric_range"
    NUMERIC_POINT = "numeric_point"
    QUALITATIVE = "qualitative"


class GuidanceComparison(StrEnum):
    WITHIN_RANGE = "within_range"
    AT_LEAST = "at_least"
    AT_MOST = "at_most"
    APPROXIMATELY = "approximately"
    NOT_APPLICABLE = "not_applicable"


class GuidanceStatus(StrEnum):
    OPEN = "open"
    DELIVERED = "delivered"
    PARTIALLY_DELIVERED = "partially_delivered"
    MISSED = "missed"
    WITHDRAWN = "withdrawn"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


class GuidanceEvaluationMethod(StrEnum):
    SYSTEM = "system"
    RULE_BASED = "rule_based"
    MANUAL = "manual"
    INTERPRETIVE = "interpretive"


class GuidanceRevisionDirection(StrEnum):
    INITIAL = "initial"
    RAISED = "raised"
    CUT = "cut"
    REAFFIRMED = "reaffirmed"
    CHANGED = "changed"


class GuidanceStatementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_id: str = Field(min_length=1, max_length=120)
    statement_type: GuidanceStatementType
    topic: str = Field(min_length=1, max_length=240)
    metric_id: str | None = Field(default=None, max_length=160, pattern=r"^[a-z][a-z0-9_.-]*$")
    statement_text: str = Field(min_length=1, max_length=5000)
    value_kind: GuidanceValueKind
    comparison: GuidanceComparison
    lower_bound: float | None = None
    upper_bound: float | None = None
    point_value: float | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=80)
    applicable_period_start: date | None = None
    applicable_period_end: date | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2300)
    fiscal_period: str | None = Field(default=None, max_length=40)
    issued_at: datetime
    known_at: datetime
    extraction_method: str = Field(min_length=1, max_length=160)
    supersedes_statement_id: str | None = Field(default=None, min_length=1, max_length=120)
    evidence_span_ids: list[str] = Field(min_length=1, max_length=50)

    @field_validator("issued_at", "known_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Guidance timestamps must include a timezone.")
        return value

    @field_validator("evidence_span_ids")
    @classmethod
    def deduplicate_evidence(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_statement(self) -> "GuidanceStatementCreate":
        if self.known_at < self.issued_at:
            raise ValueError("Guidance known_at cannot precede issued_at.")
        if (
            self.applicable_period_start
            and self.applicable_period_end
            and self.applicable_period_end < self.applicable_period_start
        ):
            raise ValueError("Guidance applicable_period_end cannot precede applicable_period_start.")
        if self.value_kind == GuidanceValueKind.NUMERIC_RANGE:
            if self.lower_bound is None or self.upper_bound is None or self.lower_bound > self.upper_bound:
                raise ValueError("Numeric range guidance requires ordered lower_bound and upper_bound values.")
            if self.point_value is not None or not self.unit or self.comparison != GuidanceComparison.WITHIN_RANGE:
                raise ValueError("Numeric range guidance must use within_range, a unit, and no point_value.")
        elif self.value_kind == GuidanceValueKind.NUMERIC_POINT:
            if self.point_value is None or not self.unit:
                raise ValueError("Numeric point guidance requires point_value and unit.")
            if self.lower_bound is not None or self.upper_bound is not None:
                raise ValueError("Numeric point guidance cannot include range bounds.")
            if self.comparison not in {
                GuidanceComparison.AT_LEAST,
                GuidanceComparison.AT_MOST,
                GuidanceComparison.APPROXIMATELY,
            }:
                raise ValueError("Numeric point guidance requires an explicit point comparison.")
        else:
            if any(value is not None for value in (self.lower_bound, self.upper_bound, self.point_value, self.unit)):
                raise ValueError("Qualitative guidance cannot be converted into numeric fields.")
            if self.comparison != GuidanceComparison.NOT_APPLICABLE:
                raise ValueError("Qualitative guidance must use not_applicable comparison.")
        return self


class GuidanceStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement_id: str
    company_id: str
    statement_type: GuidanceStatementType
    topic: str
    metric_id: str | None = None
    statement_text: str
    value_kind: GuidanceValueKind
    comparison: GuidanceComparison
    lower_bound: float | None = None
    upper_bound: float | None = None
    point_value: float | None = None
    unit: str | None = None
    applicable_period_start: date | None = None
    applicable_period_end: date | None = None
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    issued_at: datetime
    known_at: datetime
    extraction_method: str
    revision: int = Field(ge=1)
    supersedes_statement_id: str | None = None
    model_version: str = GUIDANCE_MODEL_VERSION
    created_at: datetime


class GuidanceEvaluationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    statement_id: str = Field(min_length=1, max_length=120)
    status: GuidanceStatus
    evaluated_at: datetime
    known_at: datetime
    method: GuidanceEvaluationMethod
    actual_value: float | None = None
    actual_unit: str | None = Field(default=None, min_length=1, max_length=80)
    source_fact_ids: list[str] = Field(default_factory=list, max_length=200)
    evidence_span_ids: list[str] = Field(default_factory=list, max_length=50)
    resulting_statement_id: str | None = Field(default=None, min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("evaluated_at", "known_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Guidance evaluation timestamps must include a timezone.")
        return value

    @field_validator("source_fact_ids", "evidence_span_ids")
    @classmethod
    def deduplicate_evidence(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_evaluation(self) -> "GuidanceEvaluationCreate":
        if self.known_at < self.evaluated_at:
            raise ValueError("Guidance evaluation known_at cannot precede evaluated_at.")
        if (self.actual_value is None) != (self.actual_unit is None):
            raise ValueError("Guidance actual_value and actual_unit must be supplied together.")
        if not self.source_fact_ids and not self.evidence_span_ids:
            raise ValueError("Guidance evaluation requires source facts or inspectable evidence spans.")
        if self.method in {GuidanceEvaluationMethod.MANUAL, GuidanceEvaluationMethod.INTERPRETIVE} and not self.note:
            raise ValueError("Manual or interpretive guidance evaluation requires an explanatory note.")
        return self


class GuidanceEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    statement_id: str
    status: GuidanceStatus
    evaluated_at: datetime
    known_at: datetime
    method: GuidanceEvaluationMethod
    actual_value: float | None = None
    actual_unit: str | None = None
    source_fact_ids: list[str]
    resulting_statement_id: str | None = None
    note: str | None = None
    created_at: datetime


class GuidanceWithdrawalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    known_at: datetime
    evidence_span_ids: list[str] = Field(min_length=1, max_length=50)
    note: str = Field(min_length=1, max_length=2000)

    @field_validator("known_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Guidance withdrawal known_at must include a timezone.")
        return value

    @field_validator("evidence_span_ids")
    @classmethod
    def deduplicate_evidence(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class GuidanceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link: EvidenceClaimLink
    document: EvidenceDocument
    span: EvidenceSpan


class GuidanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: GuidanceStatement
    revision_direction: GuidanceRevisionDirection
    status: GuidanceStatus
    evaluations: list[GuidanceEvaluation]
    statement_evidence: list[GuidanceEvidence]
    evaluation_evidence: dict[str, list[GuidanceEvidence]]


class GuidanceHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: CompanyIdentity
    as_of: datetime
    records: list[GuidanceRecord]
    warnings: list[str] = Field(default_factory=list)


class GuidanceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement_types: list[GuidanceStatementType] = Field(default_factory=list, max_length=4)
    statuses: list[GuidanceStatus] = Field(default_factory=list, max_length=7)
    as_of: datetime | None = None

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Guidance as_of must include a timezone.")
        return value
