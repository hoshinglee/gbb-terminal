from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from ...intelligence.collection_models import IntelligenceRefreshRequest
from ...intelligence.company_service import CompanyIntelligenceService
from ...intelligence.evidence_models import EvidenceDocumentQuery, EvidenceDocumentType
from ...intelligence.fact_models import FinancialFactQuery
from ...intelligence.estimate_models import EstimateMetric
from ...intelligence.guidance_models import GuidanceQuery, GuidanceStatementType, GuidanceStatus
from ...intelligence.models import CompanyIdentity, CompanyProvenance
from ...intelligence.operations_models import OperatingIntelligenceQuery, OperatingMetricCategory
from ...intelligence.relationship_models import (
    RelationshipConfidence,
    RelationshipDirection,
    RelationshipNetworkQuery,
    RelationshipOverrideCreate,
    RelationshipType,
)
from ..schemas.v3 import (
    CompanyLookupQuery,
    CompanyOverviewResponse,
    CompanyReferenceResponse,
    CompanyRelationshipResponse,
    FinancialFactResponse,
    FinancialHistoryQuery,
    FinancialHistoryResponse,
    EarningsAggregateResponse,
    EarningsEventAnalysisResponse,
    EarningsHistoryResponse,
    EarningsProvenanceResponse,
    EarningsQuery,
    EvidenceAsOfQuery,
    EvidenceClaimResponse,
    EvidenceClaimSpanResponse,
    EvidenceDocumentDetailResponse,
    EvidenceDocumentResponse,
    EvidenceDocumentsQuery,
    EvidenceDocumentsResponse,
    EvidenceSpanDetailResponse,
    EvidenceSpanResponse,
    GuidanceHistoryQuery,
    GuidanceHistoryResponse,
    GuidanceRecordResponse,
    EstimateComparisonResponse,
    EstimateHistoryResponse,
    EstimateProvenanceResponse,
    EstimatesQuery,
    HistoricalValuationResponse,
    IntelligenceRefreshAcceptedResponse,
    IntelligenceRefreshRequestBody,
    IntelligenceSourceHealthResponse,
    LocalJobResponse,
    MetricsProvenanceResponse,
    MetricsQuery,
    NormalizedMetricResponse,
    NormalizedMetricsResponse,
    OperatingIntelligenceResponse,
    OperatingMetricPointResponse,
    OperatingMetricSeriesResponse,
    OperationsQuery,
    ProvenanceResponse,
    SecurityMappingResponse,
    SourceEvidenceResponse,
    RelationshipEdgeResponse,
    RelationshipHistoryResponse,
    RelationshipNetworkResponse,
    RelationshipObservationResponse,
    RelationshipOverrideRequest,
    RelationshipsQuery,
    ValuationPointResponse,
    ValuationProvenanceResponse,
    ValuationQuery,
    ValuationStatisticsResponse,
)
from ...intelligence.valuation_definitions import VALUATION_DEFINITIONS
from ...storage.database import LocalMarketStore


def create_intelligence_router(
    service: CompanyIntelligenceService,
    store: LocalMarketStore | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v3", tags=["Company Intelligence"])
    refresh_tasks: set[asyncio.Task] = set()

    @router.get("/companies/{ticker}", response_model=CompanyOverviewResponse)
    async def company_overview(
        ticker: str,
        query: Annotated[CompanyLookupQuery, Query()],
    ) -> CompanyOverviewResponse:
        try:
            return _company_overview(service.company_overview(ticker, as_of=query.as_of), query.as_of)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/companies/{ticker}/financials", response_model=FinancialHistoryResponse)
    async def financial_history(
        ticker: str,
        query: Annotated[FinancialHistoryQuery, Query()],
    ) -> FinancialHistoryResponse:
        try:
            concepts = [value.strip() for value in (query.concepts or "").split(",") if value.strip()]
            forms = [value.strip().upper() for value in (query.forms or "").split(",") if value.strip()]
            result = service.financial_history(
                ticker,
                FinancialFactQuery(concepts=concepts, forms=forms, as_of=query.as_of),
                query.limit,
            )
            return FinancialHistoryResponse(
                company=_company_reference(result.company),
                as_of=result.as_of,
                matching_fact_count=result.matching_fact_count,
                returned_fact_count=len(result.facts),
                facts=[
                    FinancialFactResponse.model_validate(
                        fact.model_dump(exclude={"company_id", "cik"})
                    )
                    for fact in result.facts
                ],
                warnings=result.warnings,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/companies/{ticker}/metrics", response_model=NormalizedMetricsResponse)
    async def normalized_metrics(
        ticker: str,
        query: Annotated[MetricsQuery, Query()],
    ) -> NormalizedMetricsResponse:
        try:
            result = service.normalized_metrics(ticker, query.period, query.as_of)
            company = service.company_overview(ticker)
            source_fact_ids = list(
                dict.fromkeys(source for metric in result.metrics for source in metric.source_fact_ids)
            )
            return NormalizedMetricsResponse(
                company=_company_reference(company),
                period_kind=result.period_kind,
                as_of=result.as_of,
                definition_version=result.definition_version,
                metrics=[NormalizedMetricResponse.model_validate(metric.model_dump()) for metric in result.metrics],
                warnings=result.warnings,
                provenance=MetricsProvenanceResponse(
                    as_of=result.as_of,
                    definition_version=result.definition_version,
                    source_fact_ids=source_fact_ids,
                ),
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/companies/{ticker}/valuation", response_model=HistoricalValuationResponse)
    async def historical_valuation(
        ticker: str,
        query: Annotated[ValuationQuery, Query()],
    ) -> HistoricalValuationResponse:
        try:
            metric_ids = [value.strip() for value in (query.metrics or "").split(",") if value.strip()]
            result = await service.historical_valuation(
                ticker,
                query.period,
                query.frequency,
                query.as_of,
                metric_ids or list(VALUATION_DEFINITIONS),
            )
            company = service.company_overview(ticker)
            source_fact_ids = list(
                dict.fromkeys(
                    source
                    for points in result.points.values()
                    for point in points
                    for source in point.source_fact_ids
                )
            )
            price_source = next(
                (point.price_source for points in result.points.values() for point in points),
                "Yahoo Finance",
            )
            return HistoricalValuationResponse(
                company=_company_reference(company),
                frequency=result.frequency,
                start_date=result.start_date,
                end_date=result.end_date,
                as_of=result.as_of,
                engine_version=result.engine_version,
                history={
                    metric_id: [ValuationPointResponse.model_validate(point.model_dump()) for point in points]
                    for metric_id, points in result.points.items()
                },
                statistics={
                    metric_id: ValuationStatisticsResponse.model_validate(statistics.model_dump())
                    for metric_id, statistics in result.statistics.items()
                },
                warnings=result.warnings,
                provenance=ValuationProvenanceResponse(
                    price_source=price_source,
                    as_of=result.as_of,
                    engine_version=result.engine_version,
                    source_fact_ids=source_fact_ids,
                ),
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/companies/{ticker}/earnings", response_model=EarningsHistoryResponse)
    async def earnings_history(
        ticker: str,
        query: Annotated[EarningsQuery, Query()],
    ) -> EarningsHistoryResponse:
        try:
            result = await service.earnings_history(ticker, query.benchmark, query.as_of, query.limit)
            company = service.company_overview(ticker)
            source_fact_ids = list(
                dict.fromkeys(
                    source
                    for analysis in result.events
                    for source in analysis.event.evidence.source_fact_ids
                )
            )
            event_model_version = next(
                (analysis.event.model_version for analysis in result.events),
                "1.0.0",
            )
            reaction_engine_version = next(
                (analysis.reaction.engine_version for analysis in result.events),
                "1.0.0",
            )
            return EarningsHistoryResponse(
                company=_company_reference(company),
                benchmark_ticker=result.benchmark_ticker,
                as_of=result.as_of,
                events=[
                    EarningsEventAnalysisResponse.model_validate(analysis.model_dump())
                    for analysis in result.events
                ],
                aggregate=EarningsAggregateResponse.model_validate(result.aggregate.model_dump()),
                warnings=result.warnings,
                provenance=EarningsProvenanceResponse(
                    as_of=result.as_of,
                    event_model_version=event_model_version,
                    reaction_engine_version=reaction_engine_version,
                    source_fact_ids=source_fact_ids,
                ),
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/companies/{ticker}/estimates", response_model=EstimateHistoryResponse)
    async def estimate_history(
        ticker: str,
        query: Annotated[EstimatesQuery, Query()],
    ) -> EstimateHistoryResponse:
        try:
            raw_metrics = [value.strip() for value in (query.metrics or "").split(",") if value.strip()]
            metric_ids = [EstimateMetric(value) for value in raw_metrics] if raw_metrics else list(EstimateMetric)
            result = service.estimate_history(ticker, query.as_of, metric_ids)
            company = service.company_overview(ticker)
            return EstimateHistoryResponse(
                company=_company_reference(company),
                as_of=result.as_of,
                contract_version=result.contract_version,
                provider_key=result.provider_key,
                provider_name=result.provider_name,
                comparisons=[
                    EstimateComparisonResponse.model_validate(comparison.model_dump())
                    for comparison in result.comparisons
                ],
                warnings=result.warnings,
                provenance=EstimateProvenanceResponse(
                    provider_key=result.provider_key,
                    provider_name=result.provider_name,
                    as_of=result.as_of,
                    contract_version=result.contract_version,
                ),
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/companies/{ticker}/evidence/documents", response_model=EvidenceDocumentsResponse)
    async def evidence_documents(
        ticker: str,
        query: Annotated[EvidenceDocumentsQuery, Query()],
    ) -> EvidenceDocumentsResponse:
        try:
            raw_types = [value.strip().lower() for value in (query.types or "").split(",") if value.strip()]
            document_types = [EvidenceDocumentType(value) for value in raw_types]
            result = service.evidence_documents(
                ticker,
                EvidenceDocumentQuery(
                    document_types=document_types,
                    as_of=query.as_of,
                    limit=query.limit,
                ),
            )
            return EvidenceDocumentsResponse(
                company=_company_reference(result.company),
                as_of=result.as_of,
                matching_document_count=result.matching_document_count,
                returned_document_count=len(result.documents),
                documents=[_evidence_document(document) for document in result.documents],
                warnings=result.warnings,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get(
        "/companies/{ticker}/evidence/documents/{document_id}",
        response_model=EvidenceDocumentDetailResponse,
    )
    async def evidence_document(
        ticker: str,
        document_id: str,
        query: Annotated[EvidenceAsOfQuery, Query()],
    ) -> EvidenceDocumentDetailResponse:
        try:
            result = service.evidence_document(ticker, document_id, query.as_of)
            return EvidenceDocumentDetailResponse(
                company=_company_reference(result.company),
                as_of=result.as_of,
                document=_evidence_document(result.document),
                spans=[_evidence_span(span) for span in result.spans],
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get(
        "/companies/{ticker}/evidence/spans/{span_id}",
        response_model=EvidenceSpanDetailResponse,
    )
    async def evidence_span(
        ticker: str,
        span_id: str,
        query: Annotated[EvidenceAsOfQuery, Query()],
    ) -> EvidenceSpanDetailResponse:
        try:
            result = service.evidence_span(ticker, span_id, query.as_of)
            return EvidenceSpanDetailResponse(
                company=_company_reference(result.company),
                as_of=result.as_of,
                document=_evidence_document(result.document),
                span=_evidence_span(result.span),
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get(
        "/companies/{ticker}/evidence/claims/{claim_type}/{claim_id}",
        response_model=EvidenceClaimResponse,
    )
    async def claim_evidence(
        ticker: str,
        claim_type: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.-]*$", max_length=120)],
        claim_id: Annotated[str, Path(min_length=1, max_length=240)],
        query: Annotated[EvidenceAsOfQuery, Query()],
    ) -> EvidenceClaimResponse:
        try:
            result = service.claim_evidence(ticker, claim_type, claim_id, query.as_of)
            return EvidenceClaimResponse(
                company=_company_reference(result.company),
                as_of=result.as_of,
                claim_type=result.claim_type,
                claim_id=result.claim_id,
                evidence=[
                    EvidenceClaimSpanResponse(
                        role=item.link.role,
                        linked_at=item.link.created_at,
                        span=_evidence_span(item.span),
                    )
                    for item in result.evidence
                ],
                warnings=result.warnings,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/companies/{ticker}/relationships", response_model=RelationshipNetworkResponse)
    async def relationship_network(
        ticker: str,
        query: Annotated[RelationshipsQuery, Query()],
    ) -> RelationshipNetworkResponse:
        try:
            result = service.relationship_network(
                ticker,
                RelationshipNetworkQuery(
                    directions=_enum_values(query.directions, RelationshipDirection),
                    relationship_types=_enum_values(query.types, RelationshipType),
                    confidences=_enum_values(query.confidences, RelationshipConfidence),
                    as_of=query.as_of,
                    limit=query.limit,
                ),
            )
            return RelationshipNetworkResponse(
                company=_company_reference(result.company),
                as_of=result.as_of,
                matching_relationship_count=result.matching_relationship_count,
                returned_relationship_count=len(result.relationships),
                relationships=[_relationship(item) for item in result.relationships],
                warnings=result.warnings,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get(
        "/companies/{ticker}/relationships/{relationship_id}",
        response_model=RelationshipHistoryResponse,
    )
    async def relationship_history(
        ticker: str,
        relationship_id: str,
        query: Annotated[EvidenceAsOfQuery, Query()],
    ) -> RelationshipHistoryResponse:
        try:
            result = service.relationship_history(ticker, relationship_id, query.as_of)
            return RelationshipHistoryResponse(
                company=_company_reference(result.company),
                as_of=result.as_of,
                edge=RelationshipEdgeResponse.model_validate(result.edge.model_dump()),
                observations=[
                    RelationshipObservationResponse.model_validate(item.model_dump())
                    for item in result.observations
                ],
                evidence={
                    observation_id: [_source_evidence(item) for item in evidence]
                    for observation_id, evidence in result.evidence.items()
                },
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.post(
        "/companies/{ticker}/relationships/{relationship_id}/overrides",
        response_model=CompanyRelationshipResponse,
    )
    async def override_relationship(
        ticker: str,
        relationship_id: str,
        request: RelationshipOverrideRequest,
    ) -> CompanyRelationshipResponse:
        try:
            result = service.override_relationship(
                ticker,
                relationship_id,
                RelationshipOverrideCreate.model_validate(request.model_dump()),
            )
            return _relationship(result)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/companies/{ticker}/operations", response_model=OperatingIntelligenceResponse)
    async def operating_intelligence(
        ticker: str,
        query: Annotated[OperationsQuery, Query()],
    ) -> OperatingIntelligenceResponse:
        try:
            result = service.operating_intelligence(
                ticker,
                OperatingIntelligenceQuery(
                    categories=_enum_values(query.categories, OperatingMetricCategory),
                    as_of=query.as_of,
                ),
            )
            return OperatingIntelligenceResponse(
                company=_company_reference(result.company),
                as_of=result.as_of,
                series=[
                    OperatingMetricSeriesResponse(
                        definition=item.definition.model_dump(exclude={"company_id"}),
                        definition_evidence=[_source_evidence(evidence) for evidence in item.definition_evidence],
                        points=[
                            OperatingMetricPointResponse(
                                observation=point.observation.model_dump(),
                                mix_percent=point.mix_percent,
                                growth_percent=point.growth_percent,
                                evidence=[_source_evidence(evidence) for evidence in point.evidence],
                            )
                            for point in item.points
                        ],
                    )
                    for item in result.series
                ],
                transitions=[item.model_dump() for item in result.transitions],
                warnings=result.warnings,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/companies/{ticker}/guidance", response_model=GuidanceHistoryResponse)
    async def guidance_history(
        ticker: str,
        query: Annotated[GuidanceHistoryQuery, Query()],
    ) -> GuidanceHistoryResponse:
        try:
            result = service.guidance_history(
                ticker,
                GuidanceQuery(
                    statement_types=_enum_values(query.types, GuidanceStatementType),
                    statuses=_enum_values(query.statuses, GuidanceStatus),
                    as_of=query.as_of,
                ),
            )
            return GuidanceHistoryResponse(
                company=_company_reference(result.company),
                as_of=result.as_of,
                records=[
                    GuidanceRecordResponse(
                        statement=item.statement.model_dump(exclude={"company_id"}),
                        revision_direction=item.revision_direction,
                        status=item.status,
                        evaluations=[evaluation.model_dump() for evaluation in item.evaluations],
                        statement_evidence=[
                            _source_evidence(evidence) for evidence in item.statement_evidence
                        ],
                        evaluation_evidence={
                            evaluation_id: [_source_evidence(evidence) for evidence in evidence_items]
                            for evaluation_id, evidence_items in item.evaluation_evidence.items()
                        },
                    )
                    for item in result.records
                ],
                warnings=result.warnings,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get(
        "/companies/{ticker}/sources/health",
        response_model=IntelligenceSourceHealthResponse,
    )
    async def intelligence_source_health(ticker: str) -> IntelligenceSourceHealthResponse:
        try:
            result = service.source_health(ticker)
            return IntelligenceSourceHealthResponse.model_validate(result.model_dump())
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @router.post(
        "/companies/{ticker}/sources/refresh",
        response_model=IntelligenceRefreshAcceptedResponse,
        status_code=202,
    )
    async def refresh_intelligence_sources(
        ticker: str,
        request: IntelligenceRefreshRequestBody,
    ) -> IntelligenceRefreshAcceptedResponse:
        if store is None:
            raise HTTPException(status_code=503, detail="Local intelligence jobs are not configured.")
        symbol = ticker.strip().upper()
        command = IntelligenceRefreshRequest.model_validate(request.model_dump())
        job_id = store.create_job(
            "intelligence_refresh",
            {"ticker": symbol, **command.model_dump(mode="json")},
        )

        async def run_refresh() -> None:
            try:
                result = await asyncio.to_thread(
                    service.refresh_sources,
                    symbol,
                    command,
                    lambda value, _: store.update_job(job_id, progress=value),
                    lambda: store.job_cancellation_requested(job_id),
                )
                final_status = (
                    "cancelled"
                    if result.status.value == "cancelled"
                    else "failed"
                    if result.status.value == "failed"
                    else "completed"
                )
                store.update_job(
                    job_id,
                    result=result.model_dump(mode="json"),
                    final_status=final_status,
                )
            except Exception as error:
                store.update_job(job_id, error=str(error))

        task = asyncio.create_task(run_refresh())
        refresh_tasks.add(task)
        task.add_done_callback(refresh_tasks.discard)
        return IntelligenceRefreshAcceptedResponse(job_id=job_id)

    @router.get("/intelligence-jobs/{job_id}", response_model=LocalJobResponse)
    async def intelligence_job(job_id: str) -> LocalJobResponse:
        if store is None:
            raise HTTPException(status_code=503, detail="Local intelligence jobs are not configured.")
        result = store.get_job(job_id)
        if result is None or result["jobType"] != "intelligence_refresh":
            raise HTTPException(status_code=404, detail="Intelligence refresh job not found.")
        return LocalJobResponse.model_validate(result)

    @router.post("/intelligence-jobs/{job_id}/cancel")
    async def cancel_intelligence_job(job_id: str):
        if store is None:
            raise HTTPException(status_code=503, detail="Local intelligence jobs are not configured.")
        result = store.get_job(job_id)
        if result is None or result["jobType"] != "intelligence_refresh":
            raise HTTPException(status_code=404, detail="Intelligence refresh job not found.")
        return {"jobId": job_id, "cancelRequested": store.request_job_cancellation(job_id)}

    return router


def _provenance(value: CompanyProvenance) -> ProvenanceResponse:
    return ProvenanceResponse.model_validate(value.model_dump())


def _company_reference(company: CompanyIdentity) -> CompanyReferenceResponse:
    return CompanyReferenceResponse(
        company_id=company.company_id,
        cik=company.cik,
        legal_name=company.legal_name,
        primary_ticker=company.primary_ticker,
        exchange=company.exchange,
        status=company.status.value,
    )


def _company_overview(company: CompanyIdentity, as_of=None) -> CompanyOverviewResponse:
    return CompanyOverviewResponse(
        **_company_reference(company).model_dump(),
        as_of=as_of,
        sector=company.sector,
        industry=company.industry,
        fiscal_year_end=company.fiscal_year_end,
        securities=[
            SecurityMappingResponse(
                security_id=security.security_id,
                ticker=security.ticker,
                exchange=security.exchange,
                valid_from=security.valid_from,
                valid_to=security.valid_to,
                is_primary=security.is_primary,
                status=security.status.value,
                provenance=_provenance(security.provenance),
            )
            for security in company.securities
        ],
        provenance=_provenance(company.provenance),
    )


def _evidence_document(document) -> EvidenceDocumentResponse:
    return EvidenceDocumentResponse.model_validate(document.model_dump(exclude={"company_id"}))


def _evidence_span(span) -> EvidenceSpanResponse:
    return EvidenceSpanResponse.model_validate(span.model_dump())


def _source_evidence(item) -> SourceEvidenceResponse:
    return SourceEvidenceResponse(
        role=item.link.role,
        linked_at=item.link.created_at,
        document=_evidence_document(item.document),
        span=_evidence_span(item.span),
    )


def _relationship(item) -> CompanyRelationshipResponse:
    return CompanyRelationshipResponse(
        edge=RelationshipEdgeResponse.model_validate(item.edge.model_dump()),
        observation=RelationshipObservationResponse.model_validate(item.observation.model_dump()),
        source_company=_company_reference(item.source_company),
        target_company=_company_reference(item.target_company) if item.target_company else None,
        perspective_direction=item.perspective_direction,
        evidence=[_source_evidence(evidence) for evidence in item.evidence],
    )


def _enum_values(raw_value, enum_type):
    values = [value.strip().lower() for value in (raw_value or "").split(",") if value.strip()]
    return [enum_type(value) for value in values]
