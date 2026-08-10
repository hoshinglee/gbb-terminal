from __future__ import annotations

from datetime import datetime, timezone

from ..market_data.providers.estimates import EstimateProvider
from .estimate_models import (
    ESTIMATE_CONTRACT_VERSION,
    EstimateComparison,
    EstimateHistory,
    EstimateMatchStatus,
    EstimateMetric,
)
from .metric_models import MetricPeriodKind
from .metrics import NormalizedMetricsService


class EstimateIntelligenceService:
    def __init__(self, metrics: NormalizedMetricsService, provider: EstimateProvider) -> None:
        self.metrics = metrics
        self.provider = provider

    def history(
        self,
        ticker: str,
        as_of: datetime | None = None,
        metric_ids: list[EstimateMetric] | None = None,
    ) -> EstimateHistory:
        effective_as_of = as_of or datetime.now(timezone.utc)
        if effective_as_of.tzinfo is None or effective_as_of.utcoffset() is None:
            raise ValueError("Estimate as-of timestamps must include a timezone.")
        company = self.metrics._resolve_company(ticker)
        selected_metrics = set(metric_ids or list(EstimateMetric))
        observations = [
            observation
            for observation in self.provider.estimates(company, effective_as_of)
            if observation.metric in selected_metrics
        ]
        required_kinds = {
            MetricPeriodKind.ANNUAL if observation.fiscal_period == "FY" else MetricPeriodKind.QUARTERLY
            for observation in observations
        }
        normalized_by_kind = {
            kind: self.metrics.calculate(ticker, kind, effective_as_of)
            for kind in required_kinds
        }
        comparisons = [
            self._comparison(observation, normalized_by_kind)
            for observation in observations
        ]
        warnings = []
        if not comparisons:
            warnings.append(
                "No analyst estimate coverage is configured for this company. Reported Company Intelligence remains available."
            )
        warnings.append(
            "Estimate observations are third-party or manual expectations, not SEC-reported facts; provider and known_at remain explicit."
        )
        return EstimateHistory(
            company_id=company.company_id,
            cik=company.cik,
            ticker=company.primary_ticker or ticker.upper(),
            provider_key=self.provider.provider_key,
            provider_name=self.provider.name,
            as_of=effective_as_of.astimezone(timezone.utc),
            contract_version=ESTIMATE_CONTRACT_VERSION,
            comparisons=comparisons,
            warnings=warnings,
        )

    @staticmethod
    def _comparison(observation, normalized_by_kind):
        period_kind = (
            MetricPeriodKind.ANNUAL
            if observation.fiscal_period == "FY"
            else MetricPeriodKind.QUARTERLY
        )
        candidates = [
            metric
            for metric in normalized_by_kind[period_kind].metrics
            if metric.metric_id == observation.metric.value and metric.period_end == observation.period_end
        ]
        exact = next(
            (
                metric
                for metric in candidates
                if metric.fiscal_year == observation.fiscal_year
                and (metric.fiscal_period or "").upper() == observation.fiscal_period
            ),
            None,
        )
        if exact is None and candidates:
            return EstimateComparison(
                estimate=observation,
                match_status=EstimateMatchStatus.PERIOD_MISMATCH,
                warnings=[
                    "A reported metric shares the period end but its fiscal-year or fiscal-period label does not match the estimate."
                ],
            )
        if exact is None or exact.value is None:
            return EstimateComparison(
                estimate=observation,
                match_status=EstimateMatchStatus.UNREPORTED,
                warnings=["No exact reported fiscal-period result is available inside the requested as-of boundary."],
            )
        consensus = observation.mean if observation.mean is not None else observation.median
        difference = exact.value - consensus
        surprise = difference / abs(consensus) * 100 if consensus not in {None, 0} else None
        warnings = list(exact.warnings)
        if consensus == 0:
            warnings.append("Surprise percentage is unavailable because the consensus value is zero.")
        return EstimateComparison(
            estimate=observation,
            match_status=EstimateMatchStatus.MATCHED,
            reported_value=exact.value,
            reported_unit=exact.unit,
            reported_period_end=exact.period_end,
            reported_source_fact_ids=exact.source_fact_ids,
            difference=round(difference, 8),
            surprise_percent=round(surprise, 8) if surprise is not None else None,
            warnings=list(dict.fromkeys(warnings)),
        )
