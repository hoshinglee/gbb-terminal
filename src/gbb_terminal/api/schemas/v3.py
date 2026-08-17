from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...intelligence.collection_models import (
    DocumentCollectionStatus,
    IntelligenceRefreshStatus,
    ModuleCoverageStatus,
)
from ...intelligence.earnings_models import EarningsSession, EventTimingQuality
from ...intelligence.estimate_models import EstimateMatchStatus, EstimateMetric
from ...intelligence.evidence_models import EvidenceDocumentType, EvidenceParseStatus, EvidenceRole
from ...intelligence.guidance_models import (
    GuidanceComparison,
    GuidanceEvaluationMethod,
    GuidanceRevisionDirection,
    GuidanceStatementType,
    GuidanceStatus,
    GuidanceValueKind,
)
from ...intelligence.metric_models import MetricPeriodKind
from ...intelligence.operations_models import OperatingMetricCategory, OperatingValueType
from ...intelligence.relationship_models import (
    RelationshipConfidence,
    RelationshipDirection,
    RelationshipObservationKind,
    RelationshipType,
)
from ...intelligence.valuation_models import ValuationFrequency, ValuationStatus
from ...universe.models import UniverseKey, UniverseRefreshStatus


def _camel_case(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class V3ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=_camel_case, populate_by_name=True)


class V3QueryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class V3RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=_camel_case, populate_by_name=True)


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


class EstimatesQuery(V3QueryModel):
    metrics: str | None = Field(default=None, max_length=100)
    as_of: datetime | None = None

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("as_of must include a timezone offset.")
        return value


class EvidenceDocumentsQuery(V3QueryModel):
    types: str | None = Field(default=None, max_length=500)
    as_of: datetime | None = None
    limit: int = Field(default=100, ge=1, le=500)

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("as_of must include a timezone offset.")
        return value


class EvidenceAsOfQuery(V3QueryModel):
    as_of: datetime | None = None

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("as_of must include a timezone offset.")
        return value


class IntelligenceRefreshRequestBody(V3RequestModel):
    forms: list[str] = Field(
        default_factory=lambda: ["10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "6-K", "20-F"],
        min_length=1,
        max_length=20,
    )
    max_filings: int = Field(default=24, ge=1, le=200)
    include_exhibits: bool = True
    force: bool = False

    @field_validator("forms")
    @classmethod
    def normalize_forms(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip().upper() for value in values if value.strip()))


class IntelligenceRefreshAcceptedResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    job_id: str
    status: Literal["running"] = "running"


class IntelligenceRefreshItemResponse(V3ResponseModel):
    item_id: str
    refresh_id: str
    external_id: str
    source_url: str | None = None
    accession_number: str | None = None
    form: str | None = None
    status: DocumentCollectionStatus
    document_id: str | None = None
    reason: str | None = None
    created_at: datetime


class ModuleCoverageResponse(V3ResponseModel):
    module: str
    status: ModuleCoverageStatus
    record_count: int
    evidence_span_count: int
    message: str


class IntelligenceRefreshSummaryResponse(V3ResponseModel):
    refresh_id: str
    company_id: str
    ticker: str
    status: IntelligenceRefreshStatus
    started_at: datetime
    completed_at: datetime | None = None
    documents_discovered: int
    documents_downloaded: int
    documents_unchanged: int
    documents_parsed: int
    documents_failed: int
    relationship_count: int
    operating_observation_count: int
    guidance_statement_count: int
    coverage: list[ModuleCoverageResponse]
    items: list[IntelligenceRefreshItemResponse]
    warnings: list[str]
    model_version: str


class IntelligenceSourceHealthResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    company_id: str
    ticker: str
    last_refresh: IntelligenceRefreshSummaryResponse | None = None
    document_count: int
    parsed_document_count: int
    failed_document_count: int
    coverage: list[ModuleCoverageResponse]
    warnings: list[str]


class LocalJobResponse(V3ResponseModel):
    job_id: str
    job_type: str
    status: str
    progress: float
    request: dict
    result: dict | None = None
    error: str | None = None
    cancel_requested: bool
    created_at: datetime
    updated_at: datetime


class UniverseRefreshRequestBody(V3RequestModel):
    refresh_snapshot: bool = True
    force: bool = False
    max_companies: int | None = Field(default=None, ge=1, le=600)
    concurrency: int = Field(default=4, ge=1, le=8)
    max_attempts: int = Field(default=2, ge=1, le=3)
    fresh_hours: int = Field(default=24, ge=1, le=720)


class UniverseRefreshAcceptedResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    job_id: str
    status: Literal["running"] = "running"


class UniverseSnapshotSummaryResponse(V3ResponseModel):
    snapshot_id: str
    universe_key: UniverseKey
    version: int
    as_of_date: date
    source: str
    source_url: str
    known_at: datetime
    retrieved_at: datetime
    constituent_count: int
    quality_warnings: list[str] = Field(default_factory=list)


class UniverseRefreshSummaryResponse(V3ResponseModel):
    refresh_id: str
    universe_key: UniverseKey
    snapshot_id: str
    status: UniverseRefreshStatus
    profile: str
    total_count: int
    completed_count: int
    partial_count: int
    skipped_count: int
    failed_count: int
    cancelled_count: int
    warnings: list[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime | None = None


class UniverseStatusResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    universe_key: UniverseKey
    snapshot: UniverseSnapshotSummaryResponse | None = None
    latest_refresh: UniverseRefreshSummaryResponse | None = None
    cached_count: int
    completed_count: int
    partial_count: int
    failed_count: int
    unavailable_count: int
    sector_counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SectorConstituentResponse(V3ResponseModel):
    symbol: str
    company_name: str
    sector: str
    sub_industry: str
    company_id: str | None = None
    price: float | None = None
    daily_change_percent: float | None = None
    market_cap: float | None = None
    market_cap_source: str
    data_status: str
    observation_timestamp: datetime | None = None
    known_at: datetime | None = None
    quality_warnings: list[str] = Field(default_factory=list)


class SectorConstituentSnapshotResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    universe_key: UniverseKey
    snapshot_id: str
    sector_symbol: str
    sector_name: str
    constituent_count: int
    available_count: int
    constituents: list[SectorConstituentResponse]
    gainers: list[SectorConstituentResponse]
    losers: list[SectorConstituentResponse]
    unavailable: list[SectorConstituentResponse]
    generated_at: datetime
    warnings: list[str] = Field(default_factory=list)


class UniverseCancelResponse(V3ResponseModel):
    job_id: str
    cancel_requested: bool


class RelationshipsQuery(V3QueryModel):
    directions: str | None = Field(default=None, max_length=200)
    types: str | None = Field(default=None, max_length=500)
    confidences: str | None = Field(default=None, max_length=200)
    as_of: datetime | None = None
    limit: int = Field(default=100, ge=1, le=500)

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("as_of must include a timezone offset.")
        return value


class RelationshipOverrideRequest(V3RequestModel):
    target_company_id: str | None = Field(default=None, min_length=1, max_length=120)
    exposure_value: float | None = None
    exposure_unit: str | None = Field(default=None, min_length=1, max_length=120)
    valid_from: date | None = None
    valid_to: date | None = None
    known_at: datetime
    confidence: RelationshipConfidence
    evidence_span_ids: list[str] = Field(min_length=1, max_length=50)
    correction_note: str = Field(min_length=1, max_length=2000)

    @field_validator("known_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("knownAt must include a timezone offset.")
        return value


class OperationsQuery(V3QueryModel):
    categories: str | None = Field(default=None, max_length=200)
    as_of: datetime | None = None

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("as_of must include a timezone offset.")
        return value


class GuidanceHistoryQuery(V3QueryModel):
    types: str | None = Field(default=None, max_length=300)
    statuses: str | None = Field(default=None, max_length=300)
    as_of: datetime | None = None

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


class EvidenceDocumentResponse(V3ResponseModel):
    document_id: str
    source: str
    dataset: str
    document_type: EvidenceDocumentType
    external_id: str
    version: int
    supersedes_document_id: str | None = None
    title: str | None = None
    form: str | None = None
    accession_number: str | None = None
    source_url: str
    filed_at: datetime | None = None
    published_at: datetime | None = None
    known_at: datetime
    retrieved_at: datetime
    content_hash: str
    mime_type: str
    parse_status: EvidenceParseStatus
    parse_error: str | None = None
    source_metadata: dict
    quality_warnings: list[str]
    model_version: str
    created_at: datetime
    updated_at: datetime


class EvidenceSpanResponse(V3ResponseModel):
    span_id: str
    document_id: str
    span_hash: str
    exact_text: str
    section: str | None = None
    page_number: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    context_before: str | None = None
    context_after: str | None = None
    extraction_method: str
    extracted_at: datetime
    source_metadata: dict
    created_at: datetime


class EvidenceDocumentsResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    company: CompanyReferenceResponse
    as_of: datetime
    matching_document_count: int
    returned_document_count: int
    documents: list[EvidenceDocumentResponse]
    warnings: list[str]


class EvidenceDocumentDetailResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    company: CompanyReferenceResponse
    as_of: datetime
    document: EvidenceDocumentResponse
    spans: list[EvidenceSpanResponse]


class EvidenceSpanDetailResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    company: CompanyReferenceResponse
    as_of: datetime
    document: EvidenceDocumentResponse
    span: EvidenceSpanResponse


class EvidenceClaimSpanResponse(V3ResponseModel):
    role: EvidenceRole
    linked_at: datetime
    span: EvidenceSpanResponse


class EvidenceClaimResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    company: CompanyReferenceResponse
    as_of: datetime
    claim_type: str
    claim_id: str
    evidence: list[EvidenceClaimSpanResponse]
    warnings: list[str]


class SourceEvidenceResponse(V3ResponseModel):
    role: EvidenceRole
    linked_at: datetime
    document: EvidenceDocumentResponse
    span: EvidenceSpanResponse


class RelationshipEdgeResponse(V3ResponseModel):
    relationship_id: str
    source_company_id: str
    normalized_counterparty_name: str
    raw_counterparty_name: str
    relationship_type: RelationshipType
    direction: RelationshipDirection
    model_version: str
    created_at: datetime


class RelationshipObservationResponse(V3ResponseModel):
    observation_id: str
    relationship_id: str
    target_company_id: str | None = None
    exposure_value: float | None = None
    exposure_unit: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    known_at: datetime
    extraction_method: str
    confidence: RelationshipConfidence
    observation_kind: RelationshipObservationKind
    supersedes_observation_id: str | None = None
    correction_note: str | None = None
    created_at: datetime


class CompanyRelationshipResponse(V3ResponseModel):
    edge: RelationshipEdgeResponse
    observation: RelationshipObservationResponse
    source_company: CompanyReferenceResponse
    target_company: CompanyReferenceResponse | None = None
    perspective_direction: RelationshipDirection
    evidence: list[SourceEvidenceResponse]


class RelationshipNetworkResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    company: CompanyReferenceResponse
    as_of: datetime
    matching_relationship_count: int
    returned_relationship_count: int
    relationships: list[CompanyRelationshipResponse]
    warnings: list[str]


class RelationshipHistoryResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    company: CompanyReferenceResponse
    as_of: datetime
    edge: RelationshipEdgeResponse
    observations: list[RelationshipObservationResponse]
    evidence: dict[str, list[SourceEvidenceResponse]]


class OperatingMetricDefinitionResponse(V3ResponseModel):
    definition_id: str
    category: OperatingMetricCategory
    definition_key: str
    label: str
    measure: str
    unit: str
    value_type: OperatingValueType
    reporting_basis: str
    version: int
    valid_from: date | None = None
    valid_to: date | None = None
    supersedes_definition_id: str | None = None
    description: str | None = None
    known_at: datetime
    extraction_method: str
    model_version: str
    created_at: datetime


class OperatingMetricObservationResponse(V3ResponseModel):
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


class OperatingMetricPointResponse(V3ResponseModel):
    observation: OperatingMetricObservationResponse
    mix_percent: float | None = None
    growth_percent: float | None = None
    evidence: list[SourceEvidenceResponse]


class OperatingMetricSeriesResponse(V3ResponseModel):
    definition: OperatingMetricDefinitionResponse
    definition_evidence: list[SourceEvidenceResponse]
    points: list[OperatingMetricPointResponse]


class OperatingDefinitionTransitionResponse(V3ResponseModel):
    prior_definition_id: str
    next_definition_id: str
    definition_key: str
    prior_label: str
    next_label: str
    prior_reporting_basis: str
    next_reporting_basis: str
    known_at: datetime


class OperatingIntelligenceResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    company: CompanyReferenceResponse
    as_of: datetime
    series: list[OperatingMetricSeriesResponse]
    transitions: list[OperatingDefinitionTransitionResponse]
    warnings: list[str]


class GuidanceStatementResponse(V3ResponseModel):
    statement_id: str
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
    revision: int
    supersedes_statement_id: str | None = None
    model_version: str
    created_at: datetime


class GuidanceEvaluationResponse(V3ResponseModel):
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


class GuidanceRecordResponse(V3ResponseModel):
    statement: GuidanceStatementResponse
    revision_direction: GuidanceRevisionDirection
    status: GuidanceStatus
    evaluations: list[GuidanceEvaluationResponse]
    statement_evidence: list[SourceEvidenceResponse]
    evaluation_evidence: dict[str, list[SourceEvidenceResponse]]


class GuidanceHistoryResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    company: CompanyReferenceResponse
    as_of: datetime
    records: list[GuidanceRecordResponse]
    warnings: list[str]


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


class EstimateObservationResponse(V3ResponseModel):
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
    estimate_count: int | None = None
    observed_at: datetime
    known_at: datetime
    source_metadata: dict
    contract_version: str


class EstimateComparisonResponse(V3ResponseModel):
    estimate: EstimateObservationResponse
    match_status: EstimateMatchStatus
    reported_value: float | None = None
    reported_unit: str | None = None
    reported_period_end: date | None = None
    reported_source_fact_ids: list[str]
    difference: float | None = None
    surprise_percent: float | None = None
    warnings: list[str]


class EstimateProvenanceResponse(V3ResponseModel):
    provider_key: str
    provider_name: str
    as_of: datetime
    contract_version: str
    expectation_dataset: Literal["analyst_estimates"] = "analyst_estimates"
    reported_dataset: Literal["normalized_financial_metrics"] = "normalized_financial_metrics"
    distinction: Literal["Third-party/manual expectations are not SEC-reported facts."] = "Third-party/manual expectations are not SEC-reported facts."


class EstimateHistoryResponse(V3ResponseModel):
    api_version: Literal["v3"] = "v3"
    company: CompanyReferenceResponse
    as_of: datetime
    contract_version: str
    provider_key: str
    provider_name: str
    comparisons: list[EstimateComparisonResponse]
    warnings: list[str]
    provenance: EstimateProvenanceResponse
