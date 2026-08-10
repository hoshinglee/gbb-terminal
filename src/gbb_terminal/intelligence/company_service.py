from __future__ import annotations

from dataclasses import dataclass
import asyncio
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from .fact_models import FinancialFact, FinancialFactQuery
from .earnings import EarningsIntelligenceService
from .earnings_models import EarningsHistory
from .fact_service import FinancialFactService
from .metric_models import MetricPeriodKind, NormalizedMetricSet
from .metrics import NormalizedMetricsService
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
    ) -> None:
        self.identities = identities
        self.facts = facts
        self.metrics = metrics
        self.valuation = valuation
        self.market_data = market_data
        self.earnings = earnings

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
