from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...intelligence.earnings_models import EarningsSession, EventTimingQuality
from ...intelligence.metric_models import MetricPeriodKind
from ...intelligence.valuation_models import ValuationFrequency, ValuationStatus


def _camel_case(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class V3ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=_camel_case, populate_by_name=True)


class V3QueryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompanyLookupQuery(V3QueryModel):
    as_of: date | None = None


class FinancialHistoryQuery(V3QueryModel):
    concepts: str | None = Field(default=None, max_length=4000)
    forms: str | None = Field(default=None, max_length=500)
    as_of: datetime | None = None
    limit: int = Field(default=1000, ge=1, le=5000)

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("as_of must include a timezone offset.")
        return value


class MetricsQuery(V3QueryModel):
    period: MetricPeriodKind = MetricPeriodKind.ANNUAL
    as_of: datetime | None = None

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("as_of must include a timezone offset.")
        return value


class ValuationQuery(V3QueryModel):
    period: Literal["1y", "3y", "5y", "10y", "max"] = "5y"
    frequency: ValuationFrequency = ValuationFrequency.WEEKLY
    metrics: str | None = Field(default=None, max_length=500)
    as_of: datetime | None = None

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("as_of must include a timezone offset.")
        return value


class EarningsQuery(V3QueryModel):
    benchmark: str = Field(default="SPY", min_length=1, max_length=12, pattern=r"^[A-Za-z0-9.^=-]+$")
    as_of: datetime | None = None
    limit: int = Field(default=40, ge=1, le=100)

    @field_validator("benchmark")
    @classmethod
    def normalize_benchmark(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("as_of must include a timezone offset.")
        return value


class ProvenanceResponse(V3ResponseModel):
    source: str
    dataset: str
    observation_timestamp: datetime
    known_at: datetime
    retrieved_at: datetime
    status: str
    quality_warnings: list[str] = Field(default_factory=list)
    remaining_quota: int | None = None
    cached: bool


class SecurityMappingResponse(V3ResponseModel):
    security_id: str
    ticker: str
    exchange: str | None = None
    valid_from: date
    valid_to: date | None = None
    is_primary: bool
    status: str
    provenance: ProvenanceResponse


class CompanyReferenceResponse(V3ResponseModel):
    company_id: str
    cik: str
    legal_name: str
    primary_ticker: str | None = None
    exchange: str | None = None
    status: str


class CompanyOverviewResponse(CompanyReferenceResponse):
    api_version: Literal["v3"] = "v3"
    as_of: date | None = None
    sector: str | None = None
    industry: str | None = None
    fiscal_year_end: str | None = None
    securities: list[SecurityMappingResponse]
    provenance: ProvenanceResponse


class FinancialFactResponse(V3ResponseModel):
    fact_id: str
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
    provenance: ProvenanceResponse
    source_metadata: dict


class FinancialHistoryResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    company: CompanyReferenceResponse
    as_of: datetime
    matching_fact_count: int
    returned_fact_count: int
    facts: list[FinancialFactResponse]
    warnings: list[str] = Field(default_factory=list)


class NormalizedMetricResponse(V3ResponseModel):
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
    derived: bool
    source_fact_ids: list[str]
    warnings: list[str]


class MetricsProvenanceResponse(V3ResponseModel):
    source: Literal["SEC EDGAR"] = "SEC EDGAR"
    dataset: Literal["normalized_financial_metrics"] = "normalized_financial_metrics"
    as_of: datetime
    definition_version: str
    source_fact_ids: list[str]


class NormalizedMetricsResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    company: CompanyReferenceResponse
    period_kind: MetricPeriodKind
    as_of: datetime
    definition_version: str
    metrics: list[NormalizedMetricResponse]
    warnings: list[str]
    provenance: MetricsProvenanceResponse


class ValuationPointResponse(V3ResponseModel):
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
    source_fact_ids: list[str]
    price_source: str
    warnings: list[str]


class ValuationStatisticsResponse(V3ResponseModel):
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
    sample_size: int


class ValuationProvenanceResponse(V3ResponseModel):
    price_source: str
    price_dataset: Literal["daily_prices"] = "daily_prices"
    fundamental_source: Literal["SEC EDGAR"] = "SEC EDGAR"
    fundamental_dataset: Literal["normalized_financial_metrics"] = "normalized_financial_metrics"
    as_of: datetime
    engine_version: str
    source_fact_ids: list[str]


class HistoricalValuationResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    company: CompanyReferenceResponse
    frequency: ValuationFrequency
    start_date: date
    end_date: date
    as_of: datetime
    engine_version: str
    history: dict[str, list[ValuationPointResponse]]
    statistics: dict[str, ValuationStatisticsResponse]
    warnings: list[str]
    provenance: ValuationProvenanceResponse


class ReportedMetricResponse(V3ResponseModel):
    metric_id: str
    label: str
    value: float | None
    unit: str
    period_end: date
    source_fact_ids: list[str]
    warnings: list[str]


class EarningsEvidenceResponse(V3ResponseModel):
    source: str
    dataset: str
    accession_number: str
    filing_form: str
    filing_url: str
    filed_date: date
    known_at: datetime
    source_fact_ids: list[str]


class EarningsEventResponse(V3ResponseModel):
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
    evidence: EarningsEvidenceResponse
    reported_metrics: dict[str, ReportedMetricResponse]
    guidance_metadata: dict
    model_version: str
    warnings: list[str]


class EarningsReactionWindowResponse(V3ResponseModel):
    window: str
    end_session: date | None = None
    stock_return: float | None = None
    benchmark_return: float | None = None
    benchmark_adjusted_return: float | None = None
    status: str


class EarningsReactionPathPointResponse(V3ResponseModel):
    relative_session: int
    session_date: date
    close: float
    cumulative_return: float
    benchmark_adjusted_return: float | None = None
    volume: float | None = None


class EarningsReactionResponse(V3ResponseModel):
    event_id: str
    benchmark_ticker: str
    anchor_session: date | None = None
    prior_session: date | None = None
    opening_gap: float | None = None
    abnormal_volume: float | None = None
    volume_percentile: float | None = None
    windows: dict[str, EarningsReactionWindowResponse]
    path: list[EarningsReactionPathPointResponse]
    engine_version: str
    warnings: list[str]


class EarningsEventAnalysisResponse(V3ResponseModel):
    event: EarningsEventResponse
    reaction: EarningsReactionResponse


class EarningsAggregateResponse(V3ResponseModel):
    sample_size: int
    typical_absolute_event_move: float | None = None
    positive_reaction_frequency: float | None = None
    median_d5_return: float | None = None
    median_d20_return: float | None = None
    event_move_minimum: float | None = None
    event_move_maximum: float | None = None
    excluded_events: int


class EarningsProvenanceResponse(V3ResponseModel):
    event_source: Literal["SEC EDGAR"] = "SEC EDGAR"
    event_dataset: Literal["sec_company_facts"] = "sec_company_facts"
    price_source: Literal["Yahoo Finance"] = "Yahoo Finance"
    as_of: datetime
    event_model_version: str
    reaction_engine_version: str
    source_fact_ids: list[str]


class EarningsHistoryResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    company: CompanyReferenceResponse
    benchmark_ticker: str
    as_of: datetime
    events: list[EarningsEventAnalysisResponse]
    aggregate: EarningsAggregateResponse
    warnings: list[str]
    provenance: EarningsProvenanceResponse
