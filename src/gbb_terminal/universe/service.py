from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

import pandas as pd

from ..intelligence.earnings import EarningsIntelligenceService
from ..intelligence.fact_service import FinancialFactService
from ..intelligence.metric_models import MetricPeriodKind
from ..intelligence.metrics import NormalizedMetricsService
from ..intelligence.models import CompanyProvenance, CompanyRegistration
from ..intelligence.service import CompanyIdentityService
from ..intelligence.valuation import HistoricalValuationService
from ..intelligence.valuation_definitions import VALUATION_DEFINITIONS
from ..intelligence.valuation_models import ValuationFrequency
from ..market_data.models import DataEnvelope
from ..market_data.providers.base import ProviderUnavailable
from ..market_data.service import MarketData
from .models import (
    SectorConstituentResearch,
    SectorConstituentSnapshot,
    UniverseCompanyCache,
    UniverseConstituent,
    UniverseItemStatus,
    UniverseKey,
    UniverseRefreshRequest,
    UniverseRefreshStatus,
    UniverseRefreshSummary,
    UniverseSnapshot,
    UniverseStatus,
)
from .providers import UniverseProvider
from .repository import UniverseRepository


SECTOR_SYMBOLS = {
    "XLB": "Materials",
    "XLC": "Communication Services",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLI": "Industrials",
    "XLK": "Information Technology",
    "XLP": "Consumer Staples",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
    "XLV": "Health Care",
    "XLY": "Consumer Discretionary",
}


@dataclass(frozen=True)
class _FetchedInputs:
    history: DataEnvelope[pd.DataFrame] | None
    facts: DataEnvelope[dict] | None
    submissions: DataEnvelope[dict] | None
    errors: list[str]
    attempts: int


class UniverseResearchService:
    def __init__(
        self,
        repository: UniverseRepository,
        provider: UniverseProvider,
        identities: CompanyIdentityService,
        facts: FinancialFactService,
        metrics: NormalizedMetricsService,
        valuation: HistoricalValuationService,
        earnings: EarningsIntelligenceService,
        market_data: MarketData,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.identities = identities
        self.facts = facts
        self.metrics = metrics
        self.valuation = valuation
        self.earnings = earnings
        self.market_data = market_data

    def status(self, universe_key: UniverseKey = UniverseKey.SP500) -> UniverseStatus:
        snapshot = self.repository.latest_snapshot(universe_key)
        latest_refresh = self.repository.latest_refresh(universe_key)
        counts = self.repository.cache_counts(universe_key, snapshot.snapshot_id if snapshot else None)
        cached_count = sum(counts.values())
        warnings = []
        if snapshot is None:
            warnings.append("No local constituent snapshot exists. Download the S&P 500 research universe first.")
        else:
            warnings.extend(snapshot.quality_warnings)
        if latest_refresh:
            warnings.extend(latest_refresh.warnings)
        return UniverseStatus(
            universe_key=universe_key,
            snapshot=snapshot,
            latest_refresh=latest_refresh,
            cached_count=cached_count,
            completed_count=counts.get(UniverseItemStatus.COMPLETED.value, 0),
            partial_count=counts.get(UniverseItemStatus.PARTIAL.value, 0),
            failed_count=counts.get(UniverseItemStatus.FAILED.value, 0),
            unavailable_count=max((snapshot.constituent_count if snapshot else 0) - cached_count, 0),
            sector_counts=self.repository.sector_counts(snapshot.snapshot_id) if snapshot else {},
            warnings=list(dict.fromkeys(warnings)),
        )

    async def refresh(
        self,
        universe_key: UniverseKey = UniverseKey.SP500,
        request: UniverseRefreshRequest | None = None,
        progress: Callable[[float, str | None], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> UniverseRefreshSummary:
        command = request or UniverseRefreshRequest()
        report = progress or (lambda _value, _symbol: None)
        is_cancelled = cancelled or (lambda: False)
        warnings: list[str] = []
        snapshot = await self._snapshot(universe_key, command.refresh_snapshot, warnings)
        self._register_constituents(snapshot, warnings)
        snapshot = self.repository.get_snapshot(snapshot.snapshot_id)
        constituents = snapshot.constituents[: command.max_companies] if command.max_companies else snapshot.constituents
        refresh_id = self.repository.start_refresh(
            universe_key,
            snapshot.snapshot_id,
            command.model_dump(mode="json"),
            constituents,
        )
        benchmark, benchmark_warnings = await self._benchmark(command.max_attempts)
        warnings.extend(benchmark_warnings)
        semaphore = asyncio.Semaphore(command.concurrency)
        persistence_lock = asyncio.Lock()
        completed = 0
        completed_lock = asyncio.Lock()

        async def process(item: UniverseConstituent) -> None:
            nonlocal completed
            try:
                if is_cancelled():
                    async with persistence_lock:
                        self.repository.update_item(
                            refresh_id,
                            item.symbol,
                            company_id=item.company_id,
                            status=UniverseItemStatus.CANCELLED,
                            stage="cancelled_before_start",
                        )
                    return
                cache = self.repository.cache_record(universe_key, item.symbol)
                if not command.force and self._fresh(cache, command.fresh_hours):
                    async with persistence_lock:
                        self.repository.touch_cache_snapshot(universe_key, item.symbol, snapshot.snapshot_id)
                        self.repository.update_item(
                            refresh_id,
                            item.symbol,
                            company_id=item.company_id,
                            status=UniverseItemStatus.SKIPPED,
                            stage="fresh_cache",
                            market_cap=cache.market_cap if cache else None,
                            daily_change_percent=cache.daily_change_percent if cache else None,
                            price_observed_at=cache.observation_timestamp if cache else None,
                            price_status=cache.status.value if cache else None,
                            financial_metric_count=cache.financial_metric_count if cache else 0,
                            valuation_point_count=cache.valuation_point_count if cache else 0,
                            earnings_event_count=cache.earnings_event_count if cache else 0,
                            warnings=["Fresh local company research was retained."],
                        )
                    return
                async with persistence_lock:
                    self.repository.update_item(
                        refresh_id,
                        item.symbol,
                        company_id=item.company_id,
                        status=UniverseItemStatus.RUNNING,
                        stage="downloading",
                    )
                async with semaphore:
                    fetched = None if is_cancelled() else await self._fetch_inputs(item, command.max_attempts)
                async with persistence_lock:
                    if fetched is None or is_cancelled():
                        self.repository.update_item(
                            refresh_id,
                            item.symbol,
                            company_id=item.company_id,
                            status=UniverseItemStatus.CANCELLED,
                            stage="cancelled_after_download",
                        )
                    else:
                        self._persist_item(refresh_id, snapshot, item, fetched, benchmark)
            except Exception as error:
                warnings.append(f"{item.symbol} research failed: {error}")
                try:
                    async with persistence_lock:
                        self.repository.update_item(
                            refresh_id,
                            item.symbol,
                            company_id=item.company_id,
                            status=UniverseItemStatus.FAILED,
                            stage="processing_failed",
                            error=str(error),
                            warnings=[str(error)],
                        )
                except Exception as persistence_error:
                    warnings.append(f"{item.symbol} terminal status could not be persisted: {persistence_error}")
            finally:
                await finish_progress(item.symbol)

        async def finish_progress(symbol: str) -> None:
            nonlocal completed
            async with completed_lock:
                completed += 1
                report(completed / max(len(constituents), 1), symbol)

        results = await asyncio.gather(*(process(item) for item in constituents), return_exceptions=True)
        warnings.extend(f"Unexpected universe task failure: {result}" for result in results if isinstance(result, Exception))
        summary = self.repository.refresh_summary(refresh_id)
        incomplete = [
            item
            for item in summary.items
            if item.status in {UniverseItemStatus.QUEUED, UniverseItemStatus.RUNNING}
        ]
        for item in incomplete:
            self.repository.update_item(
                refresh_id,
                item.symbol,
                company_id=item.company_id,
                status=UniverseItemStatus.FAILED,
                stage="incomplete_reconciled",
                error="The constituent workflow ended without a terminal item status.",
                warnings=["The incomplete item was reconciled to failed instead of remaining queued or running."],
            )
        if incomplete:
            warnings.append(f"{len(incomplete)} incomplete constituent items were reconciled to failed.")
            summary = self.repository.refresh_summary(refresh_id)
        if is_cancelled() or summary.cancelled_count:
            final_status = UniverseRefreshStatus.CANCELLED
        elif summary.completed_count + summary.partial_count + summary.skipped_count == 0:
            final_status = UniverseRefreshStatus.FAILED
        elif summary.failed_count or summary.partial_count:
            final_status = UniverseRefreshStatus.PARTIAL
        else:
            final_status = UniverseRefreshStatus.COMPLETED
        report(1.0, None)
        return self.repository.finish_refresh(refresh_id, final_status, list(dict.fromkeys(warnings)))

    def sector_constituents(
        self,
        sector_symbol: str,
        universe_key: UniverseKey = UniverseKey.SP500,
    ) -> SectorConstituentSnapshot:
        snapshot = self.repository.latest_snapshot(universe_key)
        if snapshot is None:
            raise LookupError("No local S&P 500 constituent snapshot exists.")
        normalized_symbol = sector_symbol.strip().upper()
        sector_name = SECTOR_SYMBOLS.get(normalized_symbol)
        if sector_name is None:
            raise ValueError(f"Unsupported sector symbol {normalized_symbol}.")
        records = [self._sector_record(item, cache) for item, cache in self.repository.cached_constituents(snapshot.snapshot_id, sector_name)]
        available = [record for record in records if record.daily_change_percent is not None]
        gainers = sorted(
            (record for record in available if record.daily_change_percent is not None and record.daily_change_percent > 0),
            key=lambda record: record.daily_change_percent or 0,
            reverse=True,
        )[:20]
        losers = sorted(
            (record for record in available if record.daily_change_percent is not None and record.daily_change_percent < 0),
            key=lambda record: record.daily_change_percent or 0,
        )[:20]
        unavailable = [record for record in records if record.daily_change_percent is None]
        missing_market_cap = sum(record.market_cap is None for record in available)
        warnings = list(snapshot.quality_warnings)
        if unavailable:
            warnings.append(f"{len(unavailable)} constituents have no cached daily move and remain visible in the accessible list.")
        if missing_market_cap:
            warnings.append(f"{missing_market_cap} available constituents lack calculated market capitalization and use an explicitly labelled equal-area layout fallback.")
        return SectorConstituentSnapshot(
            universe_key=universe_key,
            snapshot_id=snapshot.snapshot_id,
            sector_symbol=normalized_symbol,
            sector_name=sector_name,
            constituent_count=len(records),
            available_count=len(available),
            constituents=sorted(records, key=lambda item: (item.daily_change_percent is not None, item.daily_change_percent or 0), reverse=True),
            gainers=gainers,
            losers=losers,
            unavailable=unavailable,
            generated_at=datetime.now(timezone.utc),
            warnings=list(dict.fromkeys(warnings)),
        )

    async def _snapshot(
        self,
        universe_key: UniverseKey,
        refresh_snapshot: bool,
        warnings: list[str],
    ) -> UniverseSnapshot:
        if refresh_snapshot:
            try:
                source = await asyncio.to_thread(self.provider.fetch_snapshot, universe_key)
                return self.repository.save_snapshot(source)
            except (ProviderUnavailable, ValueError) as error:
                warnings.append(str(error))
        cached = self.repository.latest_snapshot(universe_key)
        if cached is None:
            raise ValueError("No current or cached S&P 500 constituent snapshot is available.")
        warnings.append("The newest local constituent snapshot is being reused because the public source was not refreshed.")
        return cached

    def _register_constituents(self, snapshot: UniverseSnapshot, warnings: list[str]) -> None:
        provenance = CompanyProvenance(
            source=snapshot.source,
            dataset="sp500_constituents",
            observation_timestamp=datetime.combine(snapshot.as_of_date, datetime.min.time(), tzinfo=timezone.utc),
            known_at=snapshot.known_at,
            retrieved_at=snapshot.retrieved_at,
            status="Current Composition Snapshot",
            quality_warnings=snapshot.quality_warnings,
            cached=False,
        )
        for item in snapshot.constituents:
            try:
                company = self.identities.resolve_cik(item.cik)
                if company is None:
                    company = self.identities.repository.upsert_company(
                        CompanyRegistration(
                            cik=item.cik,
                            legal_name=item.company_name,
                            primary_ticker=item.symbol,
                            sector=item.sector,
                            industry=item.sub_industry,
                            effective_from=snapshot.as_of_date,
                            provenance=provenance,
                        )
                    )
                else:
                    company = self.identities.repository.enrich_classification(
                        company.company_id,
                        item.sector,
                        item.sub_industry,
                    )
                    mapped = self.identities.resolve_ticker(item.symbol)
                    if mapped is None:
                        self.identities.repository.register_security(
                            company.company_id,
                            item.symbol,
                            None,
                            snapshot.as_of_date,
                            provenance,
                        )
                    elif mapped.company_id != company.company_id:
                        raise ValueError(f"Ticker {item.symbol} resolves to a different company.")
                self.repository.link_company(snapshot.snapshot_id, item.symbol, company.company_id)
            except Exception as error:
                warnings.append(f"{item.symbol} identity was not linked: {error}")

    async def _benchmark(self, max_attempts: int) -> tuple[pd.DataFrame | None, list[str]]:
        envelope, error, _attempts = await self._fetch_with_retry(
            lambda: self.market_data.yahoo.history("SPY", "3y"),
            max_attempts,
        )
        if envelope is not None:
            self.market_data.store.save_history("SPY", envelope.data)
            self.market_data.metadata["SPY"] = envelope.metadata()
            return envelope.data, []
        cached = self.market_data.store.load_history("SPY", "3y", max_age_minutes=None)
        if cached is not None:
            return cached, [f"SPY refresh failed; cached benchmark history is used. {error}"]
        return None, [f"SPY benchmark history is unavailable; earnings reactions remain uncached. {error}"]

    async def _fetch_inputs(self, item: UniverseConstituent, max_attempts: int) -> _FetchedInputs:
        history_result, facts_result, submissions_result = await asyncio.gather(
            self._fetch_with_retry(lambda: self.market_data.yahoo.history(item.symbol, "3y"), max_attempts),
            self._fetch_with_retry(lambda: self.facts.sec.company_facts(item.cik), max_attempts),
            self._fetch_with_retry(lambda: self.facts.sec.submissions(item.cik), max_attempts),
        )
        history, history_error, history_attempts = history_result
        facts, facts_error, facts_attempts = facts_result
        submissions, submissions_error, submissions_attempts = submissions_result
        errors = [error for error in (history_error, facts_error, submissions_error) if error]
        return _FetchedInputs(
            history=history,
            facts=facts,
            submissions=submissions,
            errors=errors,
            attempts=max(history_attempts, facts_attempts, submissions_attempts),
        )

    async def _fetch_with_retry(self, loader, max_attempts: int):
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                return await asyncio.to_thread(loader), None, attempt
            except (ProviderUnavailable, ValueError) as error:
                last_error = str(error)
                if attempt < max_attempts:
                    await asyncio.sleep(0.5 * 2 ** (attempt - 1))
        return None, last_error or "Provider unavailable.", max_attempts

    def _persist_item(
        self,
        refresh_id: str,
        snapshot: UniverseSnapshot,
        item: UniverseConstituent,
        fetched: _FetchedInputs,
        benchmark: pd.DataFrame | None,
    ) -> None:
        now = datetime.now(timezone.utc)
        warnings = list(fetched.errors)
        history = fetched.history.data if fetched.history is not None else self.market_data.store.load_history(item.symbol, "3y", max_age_minutes=None)
        history_status = fetched.history.status if fetched.history is not None else "Stale Cache" if history is not None else "Unavailable"
        observation_timestamp = fetched.history.observation_timestamp if fetched.history is not None else self._history_timestamp(history)
        known_at = fetched.history.known_at if fetched.history is not None else observation_timestamp
        retrieved_at = fetched.history.retrieved_at if fetched.history is not None else now
        if fetched.history is not None:
            self.market_data.store.save_history(item.symbol, fetched.history.data)
            self.market_data.metadata[item.symbol] = fetched.history.metadata()
        elif history is not None:
            warnings.append("Serving existing local price history after a provider failure.")
        facts_envelope = fetched.facts or self._cached_envelope("sec_company_facts", item.cik, warnings)
        submissions_envelope = fetched.submissions or self._cached_envelope("sec_submissions", item.cik, warnings)
        if fetched.facts is not None:
            self.market_data.store.save_provider_payload(fetched.facts.metadata(), fetched.facts.data)
        if fetched.submissions is not None:
            self.market_data.store.save_provider_payload(fetched.submissions.metadata(), fetched.submissions.data)
        if facts_envelope is not None:
            company = self.identities.resolve_cik(item.cik)
            if company is not None:
                self.facts.ingest_company_facts(company, facts_envelope, submissions_envelope)
        metric_count = 0
        for period_kind in MetricPeriodKind:
            try:
                result = self.metrics.calculate(item.symbol, period_kind=period_kind)
                metric_count += sum(metric.value is not None for metric in result.metrics)
            except (LookupError, ValueError):
                continue
        valuation_point_count = 0
        market_cap = None
        if history is not None:
            try:
                valuation = self.valuation.calculate(
                    item.symbol,
                    history,
                    frequency=ValuationFrequency.WEEKLY,
                    metric_ids=list(VALUATION_DEFINITIONS),
                    price_source=fetched.history.source if fetched.history is not None else "Yahoo Finance",
                    price_warnings=warnings,
                )
                available_points = [point for points in valuation.points.values() for point in points if point.value is not None]
                valuation_point_count = len(available_points)
                market_cap = next((point.market_cap for point in reversed(available_points) if point.market_cap is not None), None)
            except (LookupError, ValueError) as error:
                warnings.append(f"Valuation cache unavailable: {error}")
        earnings_event_count = 0
        if history is not None and benchmark is not None and metric_count:
            try:
                earnings = self.earnings.analyze(item.symbol, history, benchmark, benchmark_ticker="SPY", limit=16)
                earnings_event_count = sum(analysis.reaction.anchor_session is not None for analysis in earnings.events)
            except (LookupError, ValueError) as error:
                warnings.append(f"Earnings context unavailable: {error}")
        price, daily_change = self._quote(history)
        provider_failed = bool(fetched.errors)
        if history is not None and metric_count > 0:
            status = UniverseItemStatus.PARTIAL if provider_failed else UniverseItemStatus.COMPLETED
        elif history is not None or metric_count > 0:
            status = UniverseItemStatus.PARTIAL
        else:
            status = UniverseItemStatus.FAILED
        company = self.identities.resolve_cik(item.cik)
        cache = UniverseCompanyCache(
            universe_key=snapshot.universe_key,
            snapshot_id=snapshot.snapshot_id,
            symbol=item.symbol,
            company_id=company.company_id if company else item.company_id,
            company_name=item.company_name,
            sector=item.sector,
            sub_industry=item.sub_industry,
            status=status,
            price=price,
            daily_change_percent=daily_change,
            market_cap=market_cap,
            market_cap_source="calculated_from_point_in_time_diluted_shares" if market_cap is not None else "unavailable_equal_area_fallback",
            observation_timestamp=observation_timestamp,
            known_at=known_at,
            retrieved_at=retrieved_at,
            financial_metric_count=metric_count,
            valuation_point_count=valuation_point_count,
            earnings_event_count=earnings_event_count,
            quality_warnings=list(dict.fromkeys(warnings)),
            last_success_at=now if status == UniverseItemStatus.COMPLETED else None,
        )
        self.repository.upsert_cache(cache)
        self.repository.update_item(
            refresh_id,
            item.symbol,
            company_id=cache.company_id,
            status=status,
            stage="complete" if status == UniverseItemStatus.COMPLETED else "partial" if status == UniverseItemStatus.PARTIAL else "failed",
            attempt_count=fetched.attempts,
            market_cap=market_cap,
            daily_change_percent=daily_change,
            price_observed_at=observation_timestamp,
            price_status=history_status,
            financial_metric_count=metric_count,
            valuation_point_count=valuation_point_count,
            earnings_event_count=earnings_event_count,
            warnings=cache.quality_warnings,
            error="; ".join(fetched.errors) if status == UniverseItemStatus.FAILED else None,
        )

    def _cached_envelope(self, dataset: str, cik: str, warnings: list[str]) -> DataEnvelope[dict] | None:
        cached = self.market_data.store.load_provider_payload(self.facts.sec.name, dataset, cik)
        if cached is None:
            return None
        metadata = cached["metadata"]
        warnings.append(f"Serving cached {dataset} after a provider failure.")
        return DataEnvelope(
            dataset=dataset,
            symbol=cik,
            data=cached["data"],
            observation_timestamp=self._timestamp(metadata["observationTimestamp"]),
            known_at=self._timestamp(metadata["knownAt"]),
            retrieved_at=self._timestamp(metadata["retrievedAt"]),
            status="Stale Cache",
            source=metadata["source"],
            quality_warnings=[*metadata.get("qualityWarnings", []), "Serving stale local cache."],
            remaining_quota=metadata.get("remainingQuota"),
            cached=True,
        )

    @staticmethod
    def _fresh(cache: UniverseCompanyCache | None, fresh_hours: int) -> bool:
        return bool(
            cache
            and cache.status == UniverseItemStatus.COMPLETED
            and cache.last_success_at
            and cache.last_success_at >= datetime.now(timezone.utc) - timedelta(hours=fresh_hours)
        )

    @staticmethod
    def _quote(history: pd.DataFrame | None) -> tuple[float | None, float | None]:
        if history is None or "Close" not in history or len(history["Close"].dropna()) < 2:
            return None, None
        close = history["Close"].dropna()
        latest, previous = float(close.iloc[-1]), float(close.iloc[-2])
        return round(latest, 4), round((latest / previous - 1) * 100, 4)

    @staticmethod
    def _history_timestamp(history: pd.DataFrame | None) -> datetime | None:
        if history is None or history.empty:
            return None
        timestamp = pd.Timestamp(history.index[-1]).to_pydatetime()
        return timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp.astimezone(timezone.utc)

    @staticmethod
    def _timestamp(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _sector_record(item: UniverseConstituent, cache: UniverseCompanyCache | None) -> SectorConstituentResearch:
        return SectorConstituentResearch(
            symbol=item.symbol,
            company_name=item.company_name,
            sector=item.sector,
            sub_industry=item.sub_industry,
            company_id=cache.company_id if cache else item.company_id,
            price=cache.price if cache else None,
            daily_change_percent=cache.daily_change_percent if cache else None,
            market_cap=cache.market_cap if cache else None,
            market_cap_source=cache.market_cap_source if cache else "unavailable_equal_area_fallback",
            data_status=cache.status.value if cache else "not_cached",
            observation_timestamp=cache.observation_timestamp if cache else None,
            known_at=cache.known_at if cache else None,
            quality_warnings=cache.quality_warnings if cache else ["This constituent has not been downloaded into the local research cache."],
        )
