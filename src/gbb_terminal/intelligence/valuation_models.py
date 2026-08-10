from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ValuationFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"


class ValuationStatus(StrEnum):
    AVAILABLE = "available"
    NOT_MEANINGFUL = "nm"
    UNAVAILABLE = "unavailable"


class ValuationPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valuation_date: date
    metric_id: str
    label: str
    value: float | None
    unit: str
    status: ValuationStatus
    price: float
    market_cap: float | None = None
    enterprise_value: float | None = None
    denominator_value: float | None = None
    denominator_metric: str
    fundamental_period_end: date | None = None
    fundamental_known_at: datetime | None = None
    source_fact_ids: list[str] = Field(default_factory=list)
    price_source: str
    warnings: list[str] = Field(default_factory=list)

    @field_validator("fundamental_known_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Fundamental known-at timestamps must include a timezone.")
        return value


class ValuationStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    label: str
    unit: str
    status: ValuationStatus
    current: float | None = None
    percentile: float | None = None
    median: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    z_score: float | None = None
    sample_size: int = 0


class ValuationSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    cik: str
    ticker: str
    frequency: ValuationFrequency
    start_date: date
    end_date: date
    as_of: datetime
    engine_version: str
    points: dict[str, list[ValuationPoint]]
    statistics: dict[str, ValuationStatistics]
    warnings: list[str] = Field(default_factory=list)

    @field_validator("as_of")
    @classmethod
    def require_as_of_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Valuation as-of timestamps must include a timezone.")
        return value
