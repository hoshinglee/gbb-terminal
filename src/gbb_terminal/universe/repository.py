from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

import duckdb

from .models import (
    UniverseCompanyCache,
    UniverseConstituent,
    UniverseItemStatus,
    UniverseKey,
    UniverseRefreshItem,
    UniverseRefreshStatus,
    UniverseRefreshSummary,
    UniverseSnapshot,
    UniverseSourceSnapshot,
)


class UniverseRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def save_snapshot(self, source: UniverseSourceSnapshot) -> UniverseSnapshot:
        existing = self.connection.execute(
            "SELECT snapshot_id FROM universe_snapshots WHERE universe_key = ? AND content_hash = ?",
            [source.universe_key.value, source.content_hash],
        ).fetchone()
        if existing:
            return self.get_snapshot(existing[0])
        version = self.connection.execute(
            "SELECT coalesce(max(version), 0) + 1 FROM universe_snapshots WHERE universe_key = ?",
            [source.universe_key.value],
        ).fetchone()[0]
        snapshot_id = hashlib.sha256(f"{source.universe_key.value}:{source.content_hash}".encode()).hexdigest()
        self.connection.execute("BEGIN TRANSACTION")
        try:
            self.connection.execute(
                """INSERT INTO universe_snapshots
                   (snapshot_id, universe_key, version, as_of_date, source, source_url, known_at, retrieved_at,
                    content_hash, constituent_count, quality_warnings, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    snapshot_id,
                    source.universe_key.value,
                    version,
                    source.as_of_date,
                    source.source,
                    source.source_url,
                    self._naive(source.known_at),
                    self._naive(source.retrieved_at),
                    source.content_hash,
                    len(source.constituents),
                    json.dumps(source.quality_warnings),
                    json.dumps(source.metadata),
                ],
            )
            self.connection.executemany(
                """INSERT INTO universe_constituents
                   (snapshot_id, symbol, source_symbol, company_name, sector, sub_industry, cik, date_added,
                    company_id, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    [
                        snapshot_id,
                        item.symbol,
                        item.source_symbol,
                        item.company_name,
                        item.sector,
                        item.sub_industry,
                        item.cik,
                        item.date_added,
                        item.company_id,
                        json.dumps(item.metadata),
                    ]
                    for item in source.constituents
                ],
            )
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        return self.get_snapshot(snapshot_id)

    def latest_snapshot(self, universe_key: UniverseKey) -> UniverseSnapshot | None:
        row = self.connection.execute(
            "SELECT snapshot_id FROM universe_snapshots WHERE universe_key = ? ORDER BY version DESC LIMIT 1",
            [universe_key.value],
        ).fetchone()
        return self.get_snapshot(row[0]) if row else None

    def get_snapshot(self, snapshot_id: str) -> UniverseSnapshot:
        row = self.connection.execute(
            """SELECT snapshot_id, universe_key, version, as_of_date, source, source_url, known_at, retrieved_at,
                      content_hash, constituent_count, quality_warnings, metadata
               FROM universe_snapshots WHERE snapshot_id = ?""",
            [snapshot_id],
        ).fetchone()
        if row is None:
            raise LookupError(f"Universe snapshot {snapshot_id} was not found.")
        constituents = self._constituents(snapshot_id)
        return UniverseSnapshot(
            snapshot_id=row[0],
            universe_key=UniverseKey(row[1]),
            version=row[2],
            as_of_date=row[3],
            source=row[4],
            source_url=row[5],
            known_at=self._aware(row[6]),
            retrieved_at=self._aware(row[7]),
            content_hash=row[8],
            constituent_count=row[9],
            constituents=constituents,
            quality_warnings=json.loads(row[10]),
            metadata=json.loads(row[11]),
        )

    def link_company(self, snapshot_id: str, symbol: str, company_id: str) -> None:
        self.connection.execute(
            "UPDATE universe_constituents SET company_id = ? WHERE snapshot_id = ? AND symbol = ?",
            [company_id, snapshot_id, symbol],
        )

    def start_refresh(
        self,
        universe_key: UniverseKey,
        snapshot_id: str,
        request: dict,
        constituents: list[UniverseConstituent],
    ) -> str:
        refresh_id = str(uuid4())
        now = self._utc_now()
        self.connection.execute("BEGIN TRANSACTION")
        try:
            self.connection.execute(
                """INSERT INTO universe_refresh_runs
                   (refresh_id, universe_key, snapshot_id, status, profile, request, total_count,
                    completed_count, partial_count, skipped_count, failed_count, cancelled_count,
                    warnings, started_at, completed_at)
                   VALUES (?, ?, ?, 'running', 'company_research', ?, ?, 0, 0, 0, 0, 0, '[]', ?, NULL)""",
                [refresh_id, universe_key.value, snapshot_id, json.dumps(request), len(constituents), now],
            )
            self.connection.executemany(
                """INSERT INTO universe_refresh_items
                   (item_id, refresh_id, symbol, company_id, status, stage, attempt_count, market_cap,
                    daily_change_percent, price_observed_at, price_status, financial_metric_count,
                    valuation_point_count, earnings_event_count, warnings, error, updated_at)
                   VALUES (?, ?, ?, ?, 'queued', 'queued', 0, NULL, NULL, NULL, NULL, 0, 0, 0, '[]', NULL, ?)""",
                [[str(uuid4()), refresh_id, item.symbol, item.company_id, now] for item in constituents],
            )
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        return refresh_id

    def update_item(
        self,
        refresh_id: str,
        symbol: str,
        *,
        company_id: str | None = None,
        status: UniverseItemStatus,
        stage: str,
        attempt_count: int = 0,
        market_cap: float | None = None,
        daily_change_percent: float | None = None,
        price_observed_at: datetime | None = None,
        price_status: str | None = None,
        financial_metric_count: int = 0,
        valuation_point_count: int = 0,
        earnings_event_count: int = 0,
        warnings: list[str] | None = None,
        error: str | None = None,
    ) -> None:
        self.connection.execute(
            """UPDATE universe_refresh_items
               SET company_id = coalesce(?, company_id), status = ?, stage = ?, attempt_count = ?,
                   market_cap = ?, daily_change_percent = ?, price_observed_at = ?, price_status = ?,
                   financial_metric_count = ?, valuation_point_count = ?, earnings_event_count = ?,
                   warnings = ?, error = ?, updated_at = ?
               WHERE refresh_id = ? AND symbol = ?""",
            [
                company_id,
                status.value,
                stage,
                attempt_count,
                market_cap,
                daily_change_percent,
                self._naive(price_observed_at) if price_observed_at else None,
                price_status,
                financial_metric_count,
                valuation_point_count,
                earnings_event_count,
                json.dumps(warnings or []),
                error,
                self._utc_now(),
                refresh_id,
                symbol,
            ],
        )

    def finish_refresh(
        self,
        refresh_id: str,
        status: UniverseRefreshStatus,
        warnings: list[str],
    ) -> UniverseRefreshSummary:
        counts = self._status_counts(refresh_id)
        self.connection.execute(
            """UPDATE universe_refresh_runs
               SET status = ?, completed_count = ?, partial_count = ?, skipped_count = ?, failed_count = ?,
                   cancelled_count = ?, warnings = ?, completed_at = ? WHERE refresh_id = ?""",
            [
                status.value,
                counts.get(UniverseItemStatus.COMPLETED.value, 0),
                counts.get(UniverseItemStatus.PARTIAL.value, 0),
                counts.get(UniverseItemStatus.SKIPPED.value, 0),
                counts.get(UniverseItemStatus.FAILED.value, 0),
                counts.get(UniverseItemStatus.CANCELLED.value, 0),
                json.dumps(warnings),
                self._utc_now(),
                refresh_id,
            ],
        )
        return self.refresh_summary(refresh_id)

    def refresh_summary(self, refresh_id: str) -> UniverseRefreshSummary:
        row = self.connection.execute(
            """SELECT refresh_id, universe_key, snapshot_id, status, profile, total_count, completed_count,
                      partial_count, skipped_count, failed_count, cancelled_count, warnings, started_at, completed_at
               FROM universe_refresh_runs WHERE refresh_id = ?""",
            [refresh_id],
        ).fetchone()
        if row is None:
            raise LookupError(f"Universe refresh {refresh_id} was not found.")
        counts = self._status_counts(refresh_id)
        return UniverseRefreshSummary(
            refresh_id=row[0],
            universe_key=UniverseKey(row[1]),
            snapshot_id=row[2],
            status=UniverseRefreshStatus(row[3]),
            profile=row[4],
            total_count=row[5],
            completed_count=counts.get(UniverseItemStatus.COMPLETED.value, row[6]),
            partial_count=counts.get(UniverseItemStatus.PARTIAL.value, row[7]),
            skipped_count=counts.get(UniverseItemStatus.SKIPPED.value, row[8]),
            failed_count=counts.get(UniverseItemStatus.FAILED.value, row[9]),
            cancelled_count=counts.get(UniverseItemStatus.CANCELLED.value, row[10]),
            items=self._refresh_items(refresh_id),
            warnings=json.loads(row[11]),
            started_at=self._aware(row[12]),
            completed_at=self._aware(row[13]) if row[13] else None,
        )

    def latest_refresh(self, universe_key: UniverseKey) -> UniverseRefreshSummary | None:
        row = self.connection.execute(
            "SELECT refresh_id FROM universe_refresh_runs WHERE universe_key = ? ORDER BY started_at DESC LIMIT 1",
            [universe_key.value],
        ).fetchone()
        return self.refresh_summary(row[0]) if row else None

    def cache_record(self, universe_key: UniverseKey, symbol: str) -> UniverseCompanyCache | None:
        row = self.connection.execute(
            """SELECT universe_key, snapshot_id, symbol, company_id, company_name, sector, sub_industry,
                      status, price, daily_change_percent, market_cap, market_cap_source,
                      observation_timestamp, known_at, retrieved_at, financial_metric_count,
                      valuation_point_count, earnings_event_count, quality_warnings, last_success_at
               FROM universe_company_cache WHERE universe_key = ? AND symbol = ?""",
            [universe_key.value, symbol],
        ).fetchone()
        return self._cache_from_row(row) if row else None

    def upsert_cache(self, record: UniverseCompanyCache) -> None:
        self.connection.execute(
            """INSERT OR REPLACE INTO universe_company_cache
               (universe_key, snapshot_id, symbol, company_id, company_name, sector, sub_industry, status,
                price, daily_change_percent, market_cap, market_cap_source, observation_timestamp, known_at,
                retrieved_at, financial_metric_count, valuation_point_count, earnings_event_count,
                quality_warnings, last_success_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                record.universe_key.value,
                record.snapshot_id,
                record.symbol,
                record.company_id,
                record.company_name,
                record.sector,
                record.sub_industry,
                record.status.value,
                record.price,
                record.daily_change_percent,
                record.market_cap,
                record.market_cap_source,
                self._naive(record.observation_timestamp) if record.observation_timestamp else None,
                self._naive(record.known_at) if record.known_at else None,
                self._naive(record.retrieved_at),
                record.financial_metric_count,
                record.valuation_point_count,
                record.earnings_event_count,
                json.dumps(record.quality_warnings),
                self._naive(record.last_success_at) if record.last_success_at else None,
            ],
        )

    def touch_cache_snapshot(self, universe_key: UniverseKey, symbol: str, snapshot_id: str) -> None:
        self.connection.execute(
            "UPDATE universe_company_cache SET snapshot_id = ? WHERE universe_key = ? AND symbol = ?",
            [snapshot_id, universe_key.value, symbol],
        )

    def cached_constituents(self, snapshot_id: str, sector: str) -> list[tuple[UniverseConstituent, UniverseCompanyCache | None]]:
        constituents = [item for item in self._constituents(snapshot_id) if item.sector == sector]
        snapshot = self.get_snapshot(snapshot_id)
        return [(item, self.cache_record(snapshot.universe_key, item.symbol)) for item in constituents]

    def cache_counts(self, universe_key: UniverseKey, snapshot_id: str | None = None) -> dict[str, int]:
        if snapshot_id is None:
            rows = self.connection.execute(
                "SELECT status, count(*) FROM universe_company_cache WHERE universe_key = ? GROUP BY status",
                [universe_key.value],
            ).fetchall()
        else:
            rows = self.connection.execute(
                """SELECT status, count(*) FROM universe_company_cache
                   WHERE universe_key = ? AND snapshot_id = ? GROUP BY status""",
                [universe_key.value, snapshot_id],
            ).fetchall()
        return {row[0]: row[1] for row in rows}

    def sector_counts(self, snapshot_id: str) -> dict[str, int]:
        rows = self.connection.execute(
            "SELECT sector, count(*) FROM universe_constituents WHERE snapshot_id = ? GROUP BY sector ORDER BY sector",
            [snapshot_id],
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    def _constituents(self, snapshot_id: str) -> list[UniverseConstituent]:
        rows = self.connection.execute(
            """SELECT symbol, source_symbol, company_name, sector, sub_industry, cik, date_added, company_id, metadata
               FROM universe_constituents WHERE snapshot_id = ? ORDER BY symbol""",
            [snapshot_id],
        ).fetchall()
        return [
            UniverseConstituent(
                symbol=row[0],
                source_symbol=row[1],
                company_name=row[2],
                sector=row[3],
                sub_industry=row[4],
                cik=row[5],
                date_added=row[6],
                company_id=row[7],
                metadata=json.loads(row[8]),
            )
            for row in rows
        ]

    def _refresh_items(self, refresh_id: str) -> list[UniverseRefreshItem]:
        rows = self.connection.execute(
            """SELECT item_id, refresh_id, symbol, company_id, status, stage, attempt_count, market_cap,
                      daily_change_percent, price_observed_at, price_status, financial_metric_count,
                      valuation_point_count, earnings_event_count, warnings, error, updated_at
               FROM universe_refresh_items WHERE refresh_id = ? ORDER BY symbol""",
            [refresh_id],
        ).fetchall()
        return [
            UniverseRefreshItem(
                item_id=row[0],
                refresh_id=row[1],
                symbol=row[2],
                company_id=row[3],
                status=UniverseItemStatus(row[4]),
                stage=row[5],
                attempt_count=row[6],
                market_cap=row[7],
                daily_change_percent=row[8],
                price_observed_at=self._aware(row[9]) if row[9] else None,
                price_status=row[10],
                financial_metric_count=row[11],
                valuation_point_count=row[12],
                earnings_event_count=row[13],
                warnings=json.loads(row[14]),
                error=row[15],
                updated_at=self._aware(row[16]),
            )
            for row in rows
        ]

    def _status_counts(self, refresh_id: str) -> dict[str, int]:
        rows = self.connection.execute(
            "SELECT status, count(*) FROM universe_refresh_items WHERE refresh_id = ? GROUP BY status",
            [refresh_id],
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    @staticmethod
    def _cache_from_row(row) -> UniverseCompanyCache:
        return UniverseCompanyCache(
            universe_key=UniverseKey(row[0]),
            snapshot_id=row[1],
            symbol=row[2],
            company_id=row[3],
            company_name=row[4],
            sector=row[5],
            sub_industry=row[6],
            status=UniverseItemStatus(row[7]),
            price=row[8],
            daily_change_percent=row[9],
            market_cap=row[10],
            market_cap_source=row[11],
            observation_timestamp=UniverseRepository._aware(row[12]) if row[12] else None,
            known_at=UniverseRepository._aware(row[13]) if row[13] else None,
            retrieved_at=UniverseRepository._aware(row[14]),
            financial_metric_count=row[15],
            valuation_point_count=row[16],
            earnings_event_count=row[17],
            quality_warnings=json.loads(row[18]),
            last_success_at=UniverseRepository._aware(row[19]) if row[19] else None,
        )

    @staticmethod
    def _naive(value: datetime) -> datetime:
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)
