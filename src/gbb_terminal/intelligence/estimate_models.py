from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ESTIMATE_CONTRACT_VERSION = "1.0.0"


class EstimateMetric(StrEnum):
    REVENUE = "revenue"
    DILUTED_EPS = "diluted_eps"


class EstimateObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    estimate_id: str
    provider_key: str
    provider_name: str
    symbol: str
    cik: str | None = None
    metric: EstimateMetric
    fiscal_year: int
    fiscal_period: str
    period_end: date
    unit: str
    mean: float | None = None
    median: float | None = None
    high: float | None = None
    low: float | None = None
    estimate_count: int | None = Field(default=None, ge=0)
    observed_at: datetime
    known_at: datetime
    source_metadata: dict = Field(default_factory=dict)
    contract_version: str = ESTIMATE_CONTRACT_VERSION

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.upper()
        if not normalized or len(normalized) > 12:
            raise ValueError("Estimate symbols must contain 1 to 12 characters.")
        return normalized

    @field_validator("fiscal_period")
    @classmethod
    def validate_fiscal_period(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"FY", "Q1", "Q2", "Q3", "Q4"}:
            raise ValueError("Estimate fiscal periods must be FY or Q1 through Q4.")
        return normalized

    @field_validator("observed_at", "known_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Estimate timestamps must include a timezone.")
        return value

    @model_validator(mode="after")
    def validate_distribution(self):
        expected_unit = {
            EstimateMetric.REVENUE: "USD",
            EstimateMetric.DILUTED_EPS: "USD/share",
        }[self.metric]
        if self.unit != expected_unit:
            raise ValueError(f"Normalized {self.metric.value} estimates must use {expected_unit}.")
        if self.mean is None and self.median is None:
            raise ValueError("An estimate observation requires a mean or median value.")
        if self.high is not None and self.low is not None and self.high < self.low:
            raise ValueError("Estimate high must be greater than or equal to estimate low.")
        if self.known_at < self.observed_at:
            raise ValueError("Estimate known_at cannot precede observed_at.")
        return self


class EstimateMatchStatus(StrEnum):
    MATCHED = "matched"
    UNREPORTED = "unreported"
    PERIOD_MISMATCH = "period_mismatch"


class EstimateComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimate: EstimateObservation
    match_status: EstimateMatchStatus
    reported_value: float | None = None
    reported_unit: str | None = None
    reported_period_end: date | None = None
    reported_source_fact_ids: list[str] = Field(default_factory=list)
    difference: float | None = None
    surprise_percent: float | None = None
    warnings: list[str] = Field(default_factory=list)


class EstimateHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    cik: str
    ticker: str
    provider_key: str
    provider_name: str
    as_of: datetime
    contract_version: str
    comparisons: list[EstimateComparison]
    warnings: list[str] = Field(default_factory=list)

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Estimate history as-of timestamps must include a timezone.")
        return value
