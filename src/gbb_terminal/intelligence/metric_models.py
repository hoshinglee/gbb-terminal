from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MetricPeriodKind(StrEnum):
    ANNUAL = "annual"
    QUARTERLY = "quarterly"
    TTM = "ttm"


class NormalizedMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    label: str
    value: float | None
    unit: str
    period_kind: MetricPeriodKind
    period_start: date | None = None
    period_end: date
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    definition_version: str
    derived: bool = False
    source_fact_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class NormalizedMetricSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    cik: str
    primary_ticker: str | None = None
    period_kind: MetricPeriodKind
    as_of: datetime
    definition_version: str
    metrics: list[NormalizedMetric]
    warnings: list[str] = Field(default_factory=list)

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Metric as-of timestamps must include a timezone.")
        return value
