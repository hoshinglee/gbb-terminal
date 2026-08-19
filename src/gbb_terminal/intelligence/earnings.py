from __future__ import annotations

import hashlib
from bisect import bisect_left
from collections import defaultdict
from datetime import date, datetime, time, timezone
from statistics import median
from zoneinfo import ZoneInfo

import pandas as pd

from .earnings_models import (
    EarningsAggregate,
    EarningsEvent,
    EarningsEventAnalysis,
    EarningsEvidence,
    EarningsHistory,
    EarningsReaction,
    EarningsReactionPathPoint,
    EarningsReactionWindow,
    EarningsSession,
    EventTimingQuality,
    ReportedMetric,
)
from .earnings_repository import EarningsRepository
from .fact_models import FinancialFactQuery
from .metric_models import MetricPeriodKind
from .metrics import NormalizedMetricsService


NEW_YORK = ZoneInfo("America/New_York")
REACTION_OFFSETS = {"d0": 0, "d1": 1, "d5": 5, "d20": 20, "d60": 60}
EVENT_METRICS = {"revenue", "diluted_eps", "gross_margin", "operating_margin", "net_income"}
EVENT_CONCEPTS = {
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "EarningsPerShareDiluted",
    "EarningsPerShareDilutedIncludingExtraordinaryItems",
    "NetIncomeLoss",
    "ProfitLoss",
}


class EarningsReactionEngine:
    def calculate(
        self,
        event: EarningsEvent,
        prices: pd.DataFrame,
        benchmark_prices: pd.DataFrame,
        benchmark_ticker: str,
        prepared: bool = False,
    ) -> EarningsReaction:
        stock = prices if prepared else self._prepare(prices)
        benchmark = benchmark_prices if prepared else self._prepare(benchmark_prices)
        warnings = []
        if stock.empty:
            return self._unavailable(event, benchmark_ticker, "No stock price history is available for this event.")
        dates = [timestamp.date() for timestamp in stock.index]
        anchor_index = self._anchor_index(event, dates, warnings)
        if anchor_index is None or anchor_index == 0:
            return self._unavailable(
                event,
                benchmark_ticker,
                "The event has no usable prior and anchor trading sessions in the selected price history.",
                warnings,
            )
        prior_index = anchor_index - 1
        prior_date = dates[prior_index]
        anchor_date = dates[anchor_index]
        prior_close = float(stock.iloc[prior_index]["Close"])
        opening_gap = None
        if "Open" in stock.columns and pd.notna(stock.iloc[anchor_index]["Open"]):
            opening_gap = self._percent(float(stock.iloc[anchor_index]["Open"]), prior_close)
        windows = {
            name: self._window(name, offset, stock, benchmark, dates, prior_index, anchor_index)
            for name, offset in REACTION_OFFSETS.items()
        }
        missing = [name for name, window in windows.items() if window.status != "available"]
        if missing:
            warnings.append(f"Insufficient forward sessions for: {', '.join(missing)}.")
        if event.session == EarningsSession.INTRADAY:
            warnings.append("Intraday timing uses the same session; D0 includes price movement before the filing timestamp.")
        abnormal_volume, volume_percentile = self._volume_context(stock, anchor_index)
        if abnormal_volume is None:
            warnings.append("Abnormal volume requires current volume and at least five prior volume observations.")
        path = self._path(stock, benchmark, dates, prior_index, anchor_index)
        return EarningsReaction(
            event_id=event.event_id,
            benchmark_ticker=benchmark_ticker.upper(),
            anchor_session=anchor_date,
            prior_session=prior_date,
            opening_gap=opening_gap,
            abnormal_volume=abnormal_volume,
            volume_percentile=volume_percentile,
            windows=windows,
            path=path,
            warnings=list(dict.fromkeys(warnings)),
        )

    @staticmethod
    def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty or "Close" not in frame.columns:
            return pd.DataFrame()
        result = frame.copy()
        result.index = pd.to_datetime(result.index).tz_localize(None).normalize()
        return result[~result.index.duplicated(keep="last")].sort_index().dropna(subset=["Close"])

    @staticmethod
    def _anchor_index(event: EarningsEvent, dates: list[date], warnings: list[str]) -> int | None:
        target = event.announcement_date
        insertion = bisect_left(dates, target)
        if insertion >= len(dates):
            return None
        if event.timing_quality == EventTimingQuality.DATE_ONLY:
            warnings.append("Exact announcement time is unavailable; the first session on or after the filing date is used.")
            return insertion
        is_trading_date = dates[insertion] == target
        if event.session == EarningsSession.AFTER_CLOSE and is_trading_date:
            return insertion + 1 if insertion + 1 < len(dates) else None
        return insertion

    def _window(self, name, offset, stock, benchmark, dates, prior_index, anchor_index):
        end_index = anchor_index + offset
        if end_index >= len(stock):
            return EarningsReactionWindow(window=name, status="insufficient_data")
        end_date = dates[end_index]
        stock_return = self._percent(float(stock.iloc[end_index]["Close"]), float(stock.iloc[prior_index]["Close"]))
        benchmark_return = self._benchmark_return(benchmark, dates[prior_index], end_date)
        return EarningsReactionWindow(
            window=name,
            end_session=end_date,
            stock_return=stock_return,
            benchmark_return=benchmark_return,
            benchmark_adjusted_return=round(stock_return - benchmark_return, 8)
            if benchmark_return is not None
            else None,
            status="available",
        )

    def _path(self, stock, benchmark, dates, prior_index, anchor_index):
        start = max(0, anchor_index - 5)
        end = min(len(stock) - 1, anchor_index + 60)
        prior_close = float(stock.iloc[prior_index]["Close"])
        points = []
        for index in range(start, end + 1):
            session_date = dates[index]
            stock_return = self._percent(float(stock.iloc[index]["Close"]), prior_close)
            benchmark_return = self._benchmark_return(benchmark, dates[prior_index], session_date)
            points.append(
                EarningsReactionPathPoint(
                    relative_session=index - anchor_index,
                    session_date=session_date,
                    close=round(float(stock.iloc[index]["Close"]), 8),
                    cumulative_return=stock_return,
                    benchmark_adjusted_return=round(stock_return - benchmark_return, 8)
                    if benchmark_return is not None
                    else None,
                    volume=round(float(stock.iloc[index]["Volume"]), 8)
                    if "Volume" in stock.columns and pd.notna(stock.iloc[index]["Volume"])
                    else None,
                )
            )
        return points

    @staticmethod
    def _benchmark_return(benchmark: pd.DataFrame, start: date, end: date) -> float | None:
        if benchmark.empty:
            return None
        try:
            start_close = benchmark.at[pd.Timestamp(start), "Close"]
            end_close = benchmark.at[pd.Timestamp(end), "Close"]
        except KeyError:
            return None
        return EarningsReactionEngine._percent(
            float(end_close),
            float(start_close),
        )

    @staticmethod
    def _volume_context(stock: pd.DataFrame, anchor_index: int) -> tuple[float | None, float | None]:
        if "Volume" not in stock.columns or pd.isna(stock.iloc[anchor_index]["Volume"]):
            return None, None
        history = stock.iloc[max(0, anchor_index - 60) : anchor_index]["Volume"].dropna()
        if len(history) < 5:
            return None, None
        recent = history.tail(20)
        baseline = float(recent.median())
        current = float(stock.iloc[anchor_index]["Volume"])
        abnormal = round(current / baseline, 8) if baseline > 0 else None
        percentile = round(float((history <= current).mean()) * 100, 4)
        return abnormal, percentile

    @staticmethod
    def _percent(end_value: float, start_value: float) -> float:
        return round((end_value / start_value - 1) * 100, 8)

    @staticmethod
    def _unavailable(
        event: EarningsEvent,
        benchmark_ticker: str,
        warning: str,
        warnings: list[str] | None = None,
    ) -> EarningsReaction:
        return EarningsReaction(
            event_id=event.event_id,
            benchmark_ticker=benchmark_ticker.upper(),
            windows={
                name: EarningsReactionWindow(window=name, status="insufficient_data")
                for name in REACTION_OFFSETS
            },
            warnings=list(dict.fromkeys([*(warnings or []), warning])),
        )


class EarningsIntelligenceService:
    def __init__(
        self,
        metrics: NormalizedMetricsService,
        repository: EarningsRepository,
        reaction_engine: EarningsReactionEngine | None = None,
    ) -> None:
        self.metrics = metrics
        self.repository = repository
        self.reaction_engine = reaction_engine or EarningsReactionEngine()

    def discover_events(self, ticker: str, as_of: datetime | None = None) -> list[EarningsEvent]:
        effective_as_of = as_of or datetime.now(timezone.utc)
        if effective_as_of.tzinfo is None or effective_as_of.utcoffset() is None:
            raise ValueError("Earnings as-of timestamps must include a timezone.")
        company = self.metrics._resolve_company(ticker)
        facts = self.metrics.facts.repository.query_facts(
            company.company_id,
            FinancialFactQuery(
                concepts=sorted(set(self.metrics.supported_concepts()) | EVENT_CONCEPTS),
                forms=["10-Q", "10-K"],
                as_of=effective_as_of,
            ),
        )
        accession_groups = defaultdict(list)
        for fact in facts:
            if fact.concept in EVENT_CONCEPTS:
                accession_groups[fact.accession_number].append(fact)
        candidates = []
        for accession, group in accession_groups.items():
            current_period_end = max(fact.period_end for fact in group)
            current_period_facts = [fact for fact in group if fact.period_end == current_period_end]
            representative = min(
                current_period_facts,
                key=lambda fact: (fact.provenance.known_at, fact.fact_id),
            )
            candidates.append(
                (
                    representative.period_end,
                    representative.fiscal_period or "",
                    representative.provenance.known_at,
                    accession,
                    current_period_facts,
                )
            )
        selected = {}
        for period_end, fiscal_period, known_at, accession, group in sorted(candidates):
            key = (period_end, fiscal_period)
            selected.setdefault(key, (known_at, accession, group))
        events = [
            self._event(
                company,
                period_end,
                fiscal_period or None,
                known_at,
                accession,
                group,
                facts,
            )
            for (period_end, fiscal_period), (known_at, accession, group) in selected.items()
        ]
        events.sort(key=lambda event: (event.announcement_date, event.event_id), reverse=True)
        self.repository.save_events(events)
        return events

    def analyze(
        self,
        ticker: str,
        prices: pd.DataFrame,
        benchmark_prices: pd.DataFrame,
        benchmark_ticker: str = "SPY",
        as_of: datetime | None = None,
        limit: int = 40,
    ) -> EarningsHistory:
        effective_as_of = as_of or datetime.now(timezone.utc)
        if effective_as_of.tzinfo is None or effective_as_of.utcoffset() is None:
            raise ValueError("Earnings as-of timestamps must include a timezone.")
        boundary = effective_as_of.astimezone(NEW_YORK).date()
        prices = prices[pd.to_datetime(prices.index).date <= boundary]
        benchmark_prices = benchmark_prices[pd.to_datetime(benchmark_prices.index).date <= boundary]
        company = self.metrics._resolve_company(ticker)
        events = self.discover_events(ticker, effective_as_of)[:limit]
        prepared_prices = self.reaction_engine._prepare(prices)
        prepared_benchmark = self.reaction_engine._prepare(benchmark_prices)
        analyses = [
            EarningsEventAnalysis(
                event=event,
                reaction=self.reaction_engine.calculate(
                    event,
                    prepared_prices,
                    prepared_benchmark,
                    benchmark_ticker,
                    prepared=True,
                ),
            )
            for event in events
        ]
        self.repository.save_reactions([analysis.reaction for analysis in analyses])
        return EarningsHistory(
            company_id=company.company_id,
            cik=company.cik,
            ticker=company.primary_ticker or ticker.upper(),
            benchmark_ticker=benchmark_ticker.upper(),
            as_of=effective_as_of.astimezone(timezone.utc),
            events=analyses,
            aggregate=self._aggregate(analyses),
            warnings=[
                "SEC filing acceptance is the initial public timing evidence and may occur after a separate earnings release.",
                "Consensus surprise and guidance comparisons are unavailable without a licensed or manually supplied estimates source.",
                "Historical earnings reactions do not predict the next earnings reaction.",
            ],
        )

    def _event(
        self,
        company,
        period_end,
        fiscal_period,
        known_at,
        accession,
        facts,
        metric_facts,
    ):
        representative = min(facts, key=lambda fact: (fact.provenance.known_at, fact.fact_id))
        accepted = representative.accepted_at
        session = self.classify_session(accepted)
        announcement_date = (
            accepted.astimezone(NEW_YORK).date() if accepted else representative.filed_date
        )
        kind = MetricPeriodKind.ANNUAL if representative.form == "10-K" else MetricPeriodKind.QUARTERLY
        metric_set = self.metrics._calculate_from_facts(
            company,
            [fact for fact in metric_facts if fact.provenance.known_at <= known_at],
            kind,
            known_at,
        )
        reported = {
            metric.metric_id: ReportedMetric(
                metric_id=metric.metric_id,
                label=metric.label,
                value=metric.value,
                unit=metric.unit,
                period_end=metric.period_end,
                source_fact_ids=metric.source_fact_ids,
                warnings=metric.warnings,
            )
            for metric in metric_set.metrics
            if metric.period_end == period_end and metric.metric_id in EVENT_METRICS
        }
        source_fact_ids = list(
            dict.fromkeys(
                [fact.fact_id for fact in facts]
                + [source for metric in reported.values() for source in metric.source_fact_ids]
            )
        )
        event_id = hashlib.sha256(
            f"{company.company_id}:{period_end.isoformat()}:{fiscal_period or ''}".encode()
        ).hexdigest()
        filing_url = self._filing_url(company.cik, accession)
        warnings = [
            "SEC filing acceptance is used as event timing; a separate earnings release may have occurred earlier."
        ]
        if accepted is None:
            warnings.append("Exact filing acceptance time is unavailable; only the filed date is known.")
        return EarningsEvent(
            event_id=event_id,
            company_id=company.company_id,
            cik=company.cik,
            ticker=company.primary_ticker or representative.cik,
            fiscal_year=representative.fiscal_year,
            fiscal_period=fiscal_period,
            period_end=period_end,
            announcement_at=accepted,
            announcement_date=announcement_date,
            session=session,
            timing_quality=EventTimingQuality.EXACT if accepted else EventTimingQuality.DATE_ONLY,
            evidence=EarningsEvidence(
                source="SEC EDGAR",
                dataset="sec_company_facts",
                accession_number=accession,
                filing_form=representative.form,
                filing_url=filing_url,
                filed_date=representative.filed_date,
                known_at=known_at,
                source_fact_ids=source_fact_ids,
            ),
            reported_metrics=reported,
            warnings=warnings,
        )

    @staticmethod
    def classify_session(announcement_at: datetime | None) -> EarningsSession:
        if announcement_at is None:
            return EarningsSession.UNKNOWN
        local = announcement_at.astimezone(NEW_YORK)
        local_time = local.time().replace(tzinfo=None)
        if local_time < time(9, 30):
            return EarningsSession.BEFORE_OPEN
        if local_time >= time(16, 0):
            return EarningsSession.AFTER_CLOSE
        return EarningsSession.INTRADAY

    @staticmethod
    def _filing_url(cik: str, accession: str) -> str:
        compact_cik = str(int(cik))
        compact_accession = accession.replace("-", "")
        return f"https://www.sec.gov/Archives/edgar/data/{compact_cik}/{compact_accession}/{accession}-index.htm"

    @staticmethod
    def _aggregate(analyses: list[EarningsEventAnalysis]) -> EarningsAggregate:
        d0 = [
            analysis.reaction.windows["d0"].stock_return
            for analysis in analyses
            if analysis.reaction.windows["d0"].stock_return is not None
        ]
        d5 = [
            analysis.reaction.windows["d5"].stock_return
            for analysis in analyses
            if analysis.reaction.windows["d5"].stock_return is not None
        ]
        d20 = [
            analysis.reaction.windows["d20"].stock_return
            for analysis in analyses
            if analysis.reaction.windows["d20"].stock_return is not None
        ]
        return EarningsAggregate(
            sample_size=len(d0),
            typical_absolute_event_move=round(median(abs(value) for value in d0), 8) if d0 else None,
            positive_reaction_frequency=round(sum(value > 0 for value in d0) / len(d0) * 100, 4) if d0 else None,
            median_d5_return=round(median(d5), 8) if d5 else None,
            median_d20_return=round(median(d20), 8) if d20 else None,
            event_move_minimum=round(min(d0), 8) if d0 else None,
            event_move_maximum=round(max(d0), 8) if d0 else None,
            excluded_events=len(analyses) - len(d0),
        )
