from __future__ import annotations

from dataclasses import dataclass
import asyncio
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from .fact_models import FinancialFact, FinancialFactQuery
from .earnings import EarningsIntelligenceService
from .earnings_models import EarningsHistory
from .estimate_models import EstimateHistory, EstimateMetric
from .estimates import EstimateIntelligenceService
from .evidence import (
    CompanyClaimEvidence,
    CompanyEvidenceDocument,
    CompanyEvidenceDocuments,
    CompanyEvidenceSpan,
    EvidenceService,
)
from .evidence_models import EvidenceDocumentQuery
from .fact_service import FinancialFactService
from .guidance import GuidanceService
from .guidance_models import GuidanceHistory, GuidanceQuery
from .metric_models import MetricPeriodKind, NormalizedMetricSet
from .metrics import NormalizedMetricsService
from .operations import OperationsIntelligenceService
from .operations_models import OperatingIntelligence, OperatingIntelligenceQuery
from .relationship_models import (
    CompanyRelationship,
    RelationshipHistory,
    RelationshipNetwork,
    RelationshipNetworkQuery,
    RelationshipOverrideCreate,
)
from .relationships import RelationshipService
from .models import CompanyIdentity
from .service import CompanyIdentityService
from .valuation import HistoricalValuationService
from .valuation_models import ValuationFrequency, ValuationSeries

if TYPE_CHECKING:
    from ..market_data.service import MarketData


@dataclass(frozen=True)
class CompanyFinancialHistory:
    company: CompanyIdentity
    as_of: datetime
    facts: list[FinancialFact]
    matching_fact_count: int
    warnings: list[str]


class CompanyIntelligenceService:
    def __init__(
        self,
        identities: CompanyIdentityService,
        facts: FinancialFactService,
        metrics: NormalizedMetricsService,
        valuation: HistoricalValuationService | None = None,
        market_data: MarketData | None = None,
        earnings: EarningsIntelligenceService | None = None,
        estimates: EstimateIntelligenceService | None = None,
        evidence: EvidenceService | None = None,
        relationships: RelationshipService | None = None,
        operations: OperationsIntelligenceService | None = None,
        guidance: GuidanceService | None = None,
    ) -> None:
        self.identities = identities
        self.facts = facts
        self.metrics = metrics
        self.valuation = valuation
        self.market_data = market_data
        self.earnings = earnings
        self.estimates = estimates
        self.evidence = evidence
        self.relationships = relationships
        self.operations = operations
        self.guidance = guidance

    def company_overview(self, ticker: str, as_of: date | None = None) -> CompanyIdentity:
        company = self.identities.resolve_ticker(ticker, as_of=as_of)
        if company is None:
            raise LookupError(f"No canonical company identity exists for ticker {ticker.upper()}.")
        return company

    def financial_history(
        self,
        ticker: str,
        query: FinancialFactQuery,
        limit: int,
    ) -> CompanyFinancialHistory:
        company = self.company_overview(ticker)
        facts = self.facts.repository.query_facts(company.company_id, query)
        warnings = []
        if len(facts) > limit:
            warnings.append(
                f"The response contains the first {limit} of {len(facts)} matching facts; narrow concepts, forms, or as_of."
            )
        effective_as_of = query.as_of or datetime.now(timezone.utc)
        return CompanyFinancialHistory(
            company=company,
            as_of=effective_as_of.astimezone(timezone.utc),
            facts=facts[:limit],
            matching_fact_count=len(facts),
            warnings=warnings,
        )

    def normalized_metrics(
        self,
        ticker: str,
        period_kind: MetricPeriodKind,
        as_of: datetime | None,
    ) -> NormalizedMetricSet:
        self.company_overview(ticker)
        return self.metrics.calculate(ticker, period_kind=period_kind, as_of=as_of)

    async def historical_valuation(
        self,
        ticker: str,
        period: str,
        frequency: ValuationFrequency,
        as_of: datetime | None,
        metric_ids: list[str],
    ) -> ValuationSeries:
        self.company_overview(ticker)
        if self.valuation is None or self.market_data is None:
            raise RuntimeError("Historical valuation is not configured for this application instance.")
        prices = await self.market_data.history(ticker, period)
        metadata = self.market_data.metadata.get(ticker.upper(), {})
        return self.valuation.calculate(
            ticker,
            prices,
            frequency=frequency,
            as_of=as_of,
            metric_ids=metric_ids,
            price_source=metadata.get("source", "Yahoo Finance"),
            price_warnings=metadata.get("qualityWarnings", []),
        )

    async def earnings_history(
        self,
        ticker: str,
        benchmark: str,
        as_of: datetime | None,
        limit: int,
    ) -> EarningsHistory:
        self.company_overview(ticker)
        if self.earnings is None or self.market_data is None:
            raise RuntimeError("Earnings intelligence is not configured for this application instance.")
        stock_prices, benchmark_prices = await asyncio.gather(
            self.market_data.history(ticker, "10y"),
            self.market_data.history(benchmark, "10y"),
        )
        result = self.earnings.analyze(
            ticker,
            stock_prices,
            benchmark_prices,
            benchmark_ticker=benchmark,
            as_of=as_of,
            limit=limit,
        )
        provider_warnings = [
            warning
            for symbol in (ticker.upper(), benchmark.upper())
            for warning in self.market_data.metadata.get(symbol, {}).get("qualityWarnings", [])
        ]
        return result.model_copy(update={"warnings": list(dict.fromkeys([*result.warnings, *provider_warnings]))})

    def estimate_history(
        self,
        ticker: str,
        as_of: datetime | None,
        metric_ids: list[EstimateMetric],
    ) -> EstimateHistory:
        self.company_overview(ticker)
        if self.estimates is None:
            raise RuntimeError("Analyst estimate intelligence is not configured for this application instance.")
        return self.estimates.history(ticker, as_of=as_of, metric_ids=metric_ids)

    def evidence_documents(
        self,
        ticker: str,
        query: EvidenceDocumentQuery,
    ) -> CompanyEvidenceDocuments:
        if self.evidence is None:
            raise RuntimeError("Evidence intelligence is not configured for this application instance.")
        return self.evidence.documents(ticker, query)

    def evidence_document(
        self,
        ticker: str,
        document_id: str,
        as_of: datetime | None = None,
    ) -> CompanyEvidenceDocument:
        if self.evidence is None:
            raise RuntimeError("Evidence intelligence is not configured for this application instance.")
        return self.evidence.document(ticker, document_id, as_of)

    def evidence_span(
        self,
        ticker: str,
        span_id: str,
        as_of: datetime | None = None,
    ) -> CompanyEvidenceSpan:
        if self.evidence is None:
            raise RuntimeError("Evidence intelligence is not configured for this application instance.")
        return self.evidence.span(ticker, span_id, as_of)

    def claim_evidence(
        self,
        ticker: str,
        claim_type: str,
        claim_id: str,
        as_of: datetime | None = None,
    ) -> CompanyClaimEvidence:
        if self.evidence is None:
            raise RuntimeError("Evidence intelligence is not configured for this application instance.")
        return self.evidence.claim(ticker, claim_type, claim_id, as_of)

    def relationship_network(
        self,
        ticker: str,
        query: RelationshipNetworkQuery,
    ) -> RelationshipNetwork:
        if self.relationships is None:
            raise RuntimeError("Relationship intelligence is not configured for this application instance.")
        return self.relationships.network(ticker, query)

    def relationship_history(
        self,
        ticker: str,
        relationship_id: str,
        as_of: datetime | None = None,
    ) -> RelationshipHistory:
        if self.relationships is None:
            raise RuntimeError("Relationship intelligence is not configured for this application instance.")
        return self.relationships.history(ticker, relationship_id, as_of)

    def override_relationship(
        self,
        ticker: str,
        relationship_id: str,
        command: RelationshipOverrideCreate,
    ) -> CompanyRelationship:
        if self.relationships is None:
            raise RuntimeError("Relationship intelligence is not configured for this application instance.")
        return self.relationships.override(ticker, relationship_id, command)

    def operating_intelligence(
        self,
        ticker: str,
        query: OperatingIntelligenceQuery,
    ) -> OperatingIntelligence:
        if self.operations is None:
            raise RuntimeError("Operating intelligence is not configured for this application instance.")
        return self.operations.history(ticker, query)

    def guidance_history(
        self,
        ticker: str,
        query: GuidanceQuery,
    ) -> GuidanceHistory:
        if self.guidance is None:
            raise RuntimeError("Guidance intelligence is not configured for this application instance.")
        return self.guidance.history(ticker, query)
