from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import duckdb
import pandas as pd

from .valuation_models import ValuationPoint


class ValuationRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def save_points(
        self,
        company_id: str,
        ticker: str,
        frequency: str,
        engine_version: str,
        points: list[ValuationPoint],
    ) -> int:
        if not points:
            return 0
        computed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [
            [
                company_id,
                ticker,
                point.valuation_date,
                frequency,
                point.metric_id,
                point.label,
                point.value,
                point.unit,
                point.status.value,
                point.price,
                point.market_cap,
                point.enterprise_value,
                point.denominator_value,
                point.denominator_metric,
                point.fundamental_period_end,
                point.fundamental_known_at.astimezone(timezone.utc).replace(tzinfo=None)
                if point.fundamental_known_at
                else None,
                json.dumps(point.source_fact_ids),
                point.price_source,
                json.dumps(point.warnings),
                engine_version,
                computed_at,
            ]
            for point in points
        ]
        columns = [
            "company_id",
            "ticker",
            "valuation_date",
            "frequency",
            "metric_id",
            "label",
            "value",
            "unit",
            "status",
            "price",
            "market_cap",
            "enterprise_value",
            "denominator_value",
            "denominator_metric",
            "fundamental_period_end",
            "fundamental_known_at",
            "source_fact_ids",
            "price_source",
            "warnings",
            "engine_version",
            "computed_at",
        ]
        relation_name = f"incoming_valuation_{uuid4().hex}"
        self.connection.register(relation_name, pd.DataFrame(rows, columns=columns))
        try:
            self.connection.execute(
                f"""INSERT OR REPLACE INTO valuation_series
                    ({", ".join(columns)})
                    SELECT {", ".join(columns)} FROM {relation_name}"""
            )
        finally:
            self.connection.unregister(relation_name)
        return len(rows)
