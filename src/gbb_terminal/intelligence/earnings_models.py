from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


EARNINGS_MODEL_VERSION = "1.0.0"
REACTION_ENGINE_VERSION = "1.0.0"


class EarningsSession(StrEnum):
    BEFORE_OPEN = "before_open"
    AFTER_CLOSE = "after_close"
    INTRADAY = "intraday"
    UNKNOWN = "unknown"


class EventTimingQuality(StrEnum):
    EXACT = "exact"
    DATE_ONLY = "date_only"


class ReportedMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    label: str
    value: float | None
    unit: str
    period_end: date
    source_fact_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EarningsEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    dataset: str
    accession_number: str
    filing_form: str
    filing_url: str
    filed_date: date
    known_at: datetime
    source_fact_ids: list[str] = Field(default_factory=list)

    @field_validator("known_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Earnings evidence known-at timestamps must include a timezone.")
        return value


class EarningsEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    company_id: str
    cik: str
    ticker: str
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    period_end: date
    announcement_at: datetime | None = None
    announcement_date: date
    session: EarningsSession
    timing_quality: EventTimingQuality
    evidence: EarningsEvidence
    reported_metrics: dict[str, ReportedMetric] = Field(default_factory=dict)
    guidance_metadata: dict = Field(default_factory=dict)
    model_version: str = EARNINGS_MODEL_VERSION
    warnings: list[str] = Field(default_factory=list)

    @field_validator("announcement_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Earnings announcement timestamps must include a timezone.")
        return value


class EarningsReactionWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window: str
    end_session: date | None = None
    stock_return: float | None = None
    benchmark_return: float | None = None
    benchmark_adjusted_return: float | None = None
    status: str


class EarningsReactionPathPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_session: int
    session_date: date
    close: float
    cumulative_return: float
    benchmark_adjusted_return: float | None = None
    volume: float | None = None


class EarningsReaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    benchmark_ticker: str
    anchor_session: date | None = None
    prior_session: date | None = None
    opening_gap: float | None = None
    abnormal_volume: float | None = None
    volume_percentile: float | None = None
    windows: dict[str, EarningsReactionWindow]
    path: list[EarningsReactionPathPoint] = Field(default_factory=list)
    engine_version: str = REACTION_ENGINE_VERSION
    warnings: list[str] = Field(default_factory=list)


class EarningsEventAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: EarningsEvent
    reaction: EarningsReaction


class EarningsAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_size: int
    typical_absolute_event_move: float | None = None
    positive_reaction_frequency: float | None = None
    median_d5_return: float | None = None
    median_d20_return: float | None = None
    event_move_minimum: float | None = None
    event_move_maximum: float | None = None
    excluded_events: int


class EarningsHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    cik: str
    ticker: str
    benchmark_ticker: str
    as_of: datetime
    events: list[EarningsEventAnalysis]
    aggregate: EarningsAggregate
    warnings: list[str] = Field(default_factory=list)

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Earnings history as-of timestamps must include a timezone.")
        return value
