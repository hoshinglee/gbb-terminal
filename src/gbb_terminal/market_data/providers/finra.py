from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone

from ..models import DataEnvelope
from .base import BaseProvider


class FINRAProvider(BaseProvider):
    name = "FINRA"

    def short_sale_volume(self, trade_date: date) -> DataEnvelope[list[dict]]:
        date_code = trade_date.strftime("%Y%m%d")
        raw = self.request_bytes(f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{date_code}.txt").decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(raw), delimiter="|"))
        known_at = datetime.combine(trade_date, datetime.max.time(), tzinfo=timezone.utc)
        retrieved_at = datetime.now(timezone.utc)
        return DataEnvelope("daily_short_sale_volume", "US", rows, known_at, known_at, retrieved_at, self.delayed_status, self.name, ["Daily short-sale volume is not short interest. FINRA short interest is published twice monthly."])

