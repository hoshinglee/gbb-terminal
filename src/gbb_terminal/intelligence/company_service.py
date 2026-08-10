from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from .fact_models import FinancialFact, FinancialFactQuery
from .fact_service import FinancialFactService
from .metric_models import MetricPeriodKind, NormalizedMetricSet
from .metrics import NormalizedMetricsService
from .models import CompanyIdentity
from .service import CompanyIdentityService


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
    ) -> None:
        self.identities = identities
        self.facts = facts
        self.metrics = metrics

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
