from __future__ import annotations

import json
from datetime import datetime, timezone

import duckdb

from .earnings_models import EarningsEvent, EarningsReaction


class EarningsRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def save_events(self, events: list[EarningsEvent]) -> int:
        if not events:
            return 0
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self.connection.executemany(
            """INSERT OR REPLACE INTO earnings_events
               (event_id, company_id, cik, ticker, fiscal_year, fiscal_period, period_end,
                announcement_at, announcement_date, session, timing_quality, evidence,
                reported_metrics, guidance_metadata, model_version, warnings, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       COALESCE((SELECT created_at FROM earnings_events WHERE event_id = ?), ?), ?)""",
            [
                [
                    event.event_id,
                    event.company_id,
                    event.cik,
                    event.ticker,
                    event.fiscal_year,
                    event.fiscal_period,
                    event.period_end,
                    event.announcement_at.astimezone(timezone.utc).replace(tzinfo=None)
                    if event.announcement_at
                    else None,
                    event.announcement_date,
                    event.session.value,
                    event.timing_quality.value,
                    event.evidence.model_dump_json(),
                    json.dumps(
                        {
                            key: value.model_dump(mode="json")
                            for key, value in event.reported_metrics.items()
                        }
                    ),
                    json.dumps(event.guidance_metadata),
                    event.model_version,
                    json.dumps(event.warnings),
                    event.event_id,
                    now,
                    now,
                ]
                for event in events
            ],
        )
        return len(events)

    def save_reactions(self, reactions: list[EarningsReaction]) -> int:
        if not reactions:
            return 0
        computed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.connection.executemany(
            """INSERT OR REPLACE INTO earnings_reactions
               (event_id, benchmark_ticker, anchor_session, prior_session, opening_gap,
                abnormal_volume, volume_percentile, windows, path, engine_version, warnings, computed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                [
                    reaction.event_id,
                    reaction.benchmark_ticker,
                    reaction.anchor_session,
                    reaction.prior_session,
                    reaction.opening_gap,
                    reaction.abnormal_volume,
                    reaction.volume_percentile,
                    json.dumps(
                        {
                            key: value.model_dump(mode="json")
                            for key, value in reaction.windows.items()
                        }
                    ),
                    json.dumps([point.model_dump(mode="json") for point in reaction.path]),
                    reaction.engine_version,
                    json.dumps(reaction.warnings),
                    computed_at,
                ]
                for reaction in reactions
            ],
        )
        return len(reactions)
