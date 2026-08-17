from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from itertools import groupby
from math import sqrt
from statistics import fmean, median, pstdev
from zoneinfo import ZoneInfo

import pandas as pd

from .fact_models import FinancialFactQuery
from .metric_models import MetricPeriodKind, NormalizedMetric
from .metrics import NormalizedMetricsService
from .valuation_definitions import (
    VALUATION_DEFINITIONS,
    VALUATION_ENGINE_VERSION,
    ValuationDefinition,
    ValuationFormula,
)
from .valuation_models import (
    ValuationFrequency,
    ValuationPoint,
    ValuationSeries,
    ValuationStatistics,
    ValuationStatus,
)
from .valuation_repository import ValuationRepository


NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class _FundamentalSnapshot:
    known_at: datetime
    period_end: date | None
    values: dict[str, NormalizedMetric]


class HistoricalValuationService:
    def __init__(
        self,
        metrics: NormalizedMetricsService,
        repository: ValuationRepository,
    ) -> None:
        self.metrics = metrics
        self.repository = repository

    def calculate(
        self,
        ticker: str,
        prices: pd.DataFrame,
        frequency: ValuationFrequency = ValuationFrequency.WEEKLY,
        as_of: datetime | None = None,
        metric_ids: list[str] | None = None,
        price_source: str = "Yahoo Finance",
        price_warnings: list[str] | None = None,
    ) -> ValuationSeries:
        effective_as_of = as_of or datetime.now(timezone.utc)
        if effective_as_of.tzinfo is None or effective_as_of.utcoffset() is None:
            raise ValueError("Valuation as-of timestamps must include a timezone.")
        company = self.metrics._resolve_company(ticker)
        selected_metrics = metric_ids or list(VALUATION_DEFINITIONS)
        unknown = sorted(set(selected_metrics) - set(VALUATION_DEFINITIONS))
        if unknown:
            raise ValueError(f"Unsupported valuation metrics: {', '.join(unknown)}.")
        frame = self._prepare_prices(prices, frequency, effective_as_of)
        if frame.empty:
            raise ValueError(f"No price observations are available for {ticker.upper()} within the requested as-of boundary.")
        price_dates = [timestamp.date() for timestamp in frame.index]
        close_times = [self.market_close(day) for day in price_dates]
        snapshots = self._snapshots(company, close_times[0], close_times[-1])
        snapshot_times = [snapshot.known_at for snapshot in snapshots]
        grouped: dict[str, list[ValuationPoint]] = {metric_id: [] for metric_id in selected_metrics}
        common_warnings = list(price_warnings or [])
        if frequency == ValuationFrequency.WEEKLY:
            common_warnings.append("Weekly history uses the last available trading session in each Friday-ending week.")
        for (_, row), valuation_date, close_time in zip(frame.iterrows(), price_dates, close_times, strict=True):
            snapshot_index = bisect_right(snapshot_times, close_time) - 1
            snapshot = snapshots[snapshot_index] if snapshot_index >= 0 else None
            price = float(row["Close"])
            for metric_id in selected_metrics:
                grouped[metric_id].append(
                    self._point(
                        valuation_date,
                        price,
                        VALUATION_DEFINITIONS[metric_id],
                        snapshot,
                        price_source,
                    )
                )
        all_points = [point for points in grouped.values() for point in points]
        self.repository.save_points(
            company.company_id,
            company.primary_ticker or ticker.upper(),
            frequency.value,
            VALUATION_ENGINE_VERSION,
            all_points,
        )
        return ValuationSeries(
            company_id=company.company_id,
            cik=company.cik,
            ticker=company.primary_ticker or ticker.upper(),
            frequency=frequency,
            start_date=price_dates[0],
            end_date=price_dates[-1],
            as_of=effective_as_of.astimezone(timezone.utc),
            engine_version=VALUATION_ENGINE_VERSION,
            points=grouped,
            statistics={metric_id: self._statistics(metric_id, points) for metric_id, points in grouped.items()},
            warnings=list(dict.fromkeys(common_warnings)),
        )

    @staticmethod
    def market_close(value: date) -> datetime:
        return datetime.combine(value, time(16, 0), tzinfo=NEW_YORK).astimezone(timezone.utc)

    @staticmethod
    def _prepare_prices(
        prices: pd.DataFrame,
        frequency: ValuationFrequency,
        as_of: datetime,
    ) -> pd.DataFrame:
        if "Close" not in prices.columns:
            raise ValueError("Price history must include a Close column.")
        frame = prices.copy()
        frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
        frame = frame[~frame.index.duplicated(keep="last")].sort_index()
        frame = frame[frame.index.date <= as_of.astimezone(NEW_YORK).date()]
        frame = frame.dropna(subset=["Close"])
        if frequency == ValuationFrequency.WEEKLY and not frame.empty:
            frame = frame.groupby(frame.index.to_period("W-FRI"), sort=True).tail(1)
        return frame

    def _snapshots(
        self,
        company,
        minimum_known_at: datetime,
        maximum_known_at: datetime,
    ) -> list[_FundamentalSnapshot]:
        facts = self.metrics.facts.repository.query_facts(
            company.company_id,
            FinancialFactQuery(
                concepts=self.metrics.supported_concepts(),
                as_of=maximum_known_at,
            ),
        )
        snapshots = []
        ordered_facts = sorted(
            facts,
            key=lambda fact: (fact.provenance.known_at, fact.fact_id),
        )
        visible_facts = [fact for fact in ordered_facts if fact.provenance.known_at <= minimum_known_at]
        if visible_facts:
            baseline_known_at = max(fact.provenance.known_at for fact in visible_facts)
            snapshots.append(self._fundamental_snapshot(company, visible_facts, baseline_known_at))
        for known_at, new_facts in groupby(
            (fact for fact in ordered_facts if fact.provenance.known_at > minimum_known_at),
            key=lambda fact: fact.provenance.known_at,
        ):
            visible_facts.extend(new_facts)
            snapshots.append(self._fundamental_snapshot(company, visible_facts, known_at))
        return snapshots

    def _fundamental_snapshot(
        self,
        company,
        visible_facts,
        known_at: datetime,
    ) -> _FundamentalSnapshot:
        result = self.metrics._calculate_from_facts(
            company,
            visible_facts,
            MetricPeriodKind.TTM,
            known_at,
        )
        latest_period_end = max((metric.period_end for metric in result.metrics), default=None)
        values = {
            metric.metric_id: metric
            for metric in result.metrics
            if latest_period_end is not None and metric.period_end == latest_period_end
        }
        return _FundamentalSnapshot(known_at, latest_period_end, values)

    def _point(
        self,
        valuation_date: date,
        price: float,
        definition: ValuationDefinition,
        snapshot: _FundamentalSnapshot | None,
        price_source: str,
    ) -> ValuationPoint:
        warnings = []
        if snapshot is None:
            return self._unavailable_point(
                valuation_date,
                price,
                definition,
                price_source,
                "No SEC fundamentals were known by the market close used for this valuation date.",
            )
        values = snapshot.values
        shares = values.get("diluted_shares")
        denominator = values.get(definition.denominator_metric)
        cash = values.get("cash")
        debt = values.get("debt")
        source_metrics = [metric for metric in (shares, denominator, cash, debt) if metric is not None]
        source_ids = list(dict.fromkeys(source for metric in source_metrics for source in metric.source_fact_ids))
        if shares is None or shares.value is None or shares.value <= 0:
            return self._unavailable_point(
                valuation_date,
                price,
                definition,
                price_source,
                "A positive point-in-time diluted share count is required.",
                snapshot,
                source_ids,
            )
        market_cap = price * shares.value
        enterprise_value = None
        if debt is not None and cash is not None and debt.value is not None and cash.value is not None:
            enterprise_value = market_cap + debt.value - cash.value
        if denominator is None or denominator.value is None:
            return self._unavailable_point(
                valuation_date,
                price,
                definition,
                price_source,
                f"{definition.label} requires point-in-time {definition.denominator_metric.replace('_', ' ')}.",
                snapshot,
                source_ids,
                market_cap,
                enterprise_value,
            )
        if definition.formula != ValuationFormula.YIELD and denominator.value <= 0:
            return ValuationPoint(
                valuation_date=valuation_date,
                metric_id=definition.metric_id,
                label=definition.label,
                value=None,
                unit=definition.unit,
                status=ValuationStatus.NOT_MEANINGFUL,
                price=round(price, 8),
                market_cap=round(market_cap, 8),
                enterprise_value=round(enterprise_value, 8) if enterprise_value is not None else None,
                denominator_value=round(denominator.value, 8),
                denominator_metric=definition.denominator_metric,
                fundamental_period_end=snapshot.period_end,
                fundamental_known_at=snapshot.known_at,
                source_fact_ids=source_ids,
                price_source=price_source,
                warnings=[f"{definition.label} is not meaningful because its denominator is zero or negative."],
            )
        if definition.formula == ValuationFormula.ENTERPRISE_VALUE_RATIO and enterprise_value is None:
            return self._unavailable_point(
                valuation_date,
                price,
                definition,
                price_source,
                f"{definition.label} requires point-in-time cash and debt.",
                snapshot,
                source_ids,
                market_cap,
            )
        if definition.formula == ValuationFormula.MARKET_CAP_RATIO:
            value = market_cap / denominator.value
        elif definition.formula == ValuationFormula.ENTERPRISE_VALUE_RATIO:
            value = enterprise_value / denominator.value
        else:
            value = denominator.value / market_cap * 100
        warnings.extend(warning for metric in source_metrics for warning in metric.warnings)
        return ValuationPoint(
            valuation_date=valuation_date,
            metric_id=definition.metric_id,
            label=definition.label,
            value=round(value, 8),
            unit=definition.unit,
            status=ValuationStatus.AVAILABLE,
            price=round(price, 8),
            market_cap=round(market_cap, 8),
            enterprise_value=round(enterprise_value, 8) if enterprise_value is not None else None,
            denominator_value=round(denominator.value, 8),
            denominator_metric=definition.denominator_metric,
            fundamental_period_end=snapshot.period_end,
            fundamental_known_at=snapshot.known_at,
            source_fact_ids=source_ids,
            price_source=price_source,
            warnings=list(dict.fromkeys(warnings)),
        )

    @staticmethod
    def _unavailable_point(
        valuation_date: date,
        price: float,
        definition: ValuationDefinition,
        price_source: str,
        warning: str,
        snapshot: _FundamentalSnapshot | None = None,
        source_ids: list[str] | None = None,
        market_cap: float | None = None,
        enterprise_value: float | None = None,
    ) -> ValuationPoint:
        return ValuationPoint(
            valuation_date=valuation_date,
            metric_id=definition.metric_id,
            label=definition.label,
            value=None,
            unit=definition.unit,
            status=ValuationStatus.UNAVAILABLE,
            price=round(price, 8),
            market_cap=round(market_cap, 8) if market_cap is not None else None,
            enterprise_value=round(enterprise_value, 8) if enterprise_value is not None else None,
            denominator_metric=definition.denominator_metric,
            fundamental_period_end=snapshot.period_end if snapshot else None,
            fundamental_known_at=snapshot.known_at if snapshot else None,
            source_fact_ids=source_ids or [],
            price_source=price_source,
            warnings=[warning],
        )

    @staticmethod
    def _statistics(metric_id: str, points: list[ValuationPoint]) -> ValuationStatistics:
        definition = VALUATION_DEFINITIONS[metric_id]
        values = [point.value for point in points if point.status == ValuationStatus.AVAILABLE and point.value is not None]
        if not values:
            current_status = points[-1].status if points else ValuationStatus.UNAVAILABLE
            return ValuationStatistics(
                metric_id=metric_id,
                label=definition.label,
                unit=definition.unit,
                status=current_status,
            )
        current_point = next(
            (point for point in reversed(points) if point.status == ValuationStatus.AVAILABLE and point.value is not None),
            None,
        )
        current = current_point.value
        deviation = pstdev(values) if len(values) > 1 else 0
        return ValuationStatistics(
            metric_id=metric_id,
            label=definition.label,
            unit=definition.unit,
            status=points[-1].status,
            current=current,
            percentile=round(sum(value <= current for value in values) / len(values) * 100, 4),
            median=round(median(values), 8),
            minimum=round(min(values), 8),
            maximum=round(max(values), 8),
            z_score=round((current - fmean(values)) / deviation, 8) if deviation > sqrt(1e-20) else None,
            sample_size=len(values),
        )
