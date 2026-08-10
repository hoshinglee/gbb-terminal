from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from ...intelligence.company_service import CompanyIntelligenceService
from ...intelligence.fact_models import FinancialFactQuery
from ...intelligence.estimate_models import EstimateMetric
from ...intelligence.models import CompanyIdentity, CompanyProvenance
from ..schemas.v3 import (
    CompanyLookupQuery,
    CompanyOverviewResponse,
    CompanyReferenceResponse,
    FinancialFactResponse,
    FinancialHistoryQuery,
    FinancialHistoryResponse,
    EarningsAggregateResponse,
    EarningsEventAnalysisResponse,
    EarningsHistoryResponse,
    EarningsProvenanceResponse,
    EarningsQuery,
    EstimateComparisonResponse,
    EstimateHistoryResponse,
    EstimateProvenanceResponse,
    EstimatesQuery,
    HistoricalValuationResponse,
    MetricsProvenanceResponse,
    MetricsQuery,
    NormalizedMetricResponse,
    NormalizedMetricsResponse,
    ProvenanceResponse,
    SecurityMappingResponse,
    ValuationPointResponse,
    ValuationProvenanceResponse,
    ValuationQuery,
    ValuationStatisticsResponse,
)
from ...intelligence.valuation_definitions import VALUATION_DEFINITIONS


def create_intelligence_router(service: CompanyIntelligenceService) -> APIRouter:
    router = APIRouter(prefix="/api/v3", tags=["Company Intelligence"])

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
