from __future__ import annotations

from datetime import datetime, timezone

from ..models import DataEnvelope
from .base import BaseProvider


class OCCProvider(BaseProvider):
    name = "Options Clearing Corporation"

    def report_catalogue(self) -> DataEnvelope[dict]:
        now = datetime.now(timezone.utc)
        data = {"volumeAndOpenInterest": "https://www.theocc.com/market-data/market-data-reports/volume-and-open-interest/volume-query"}
        return DataEnvelope("aggregate_options_context", "US", data, now, now, now, self.delayed_status, self.name, ["OCC aggregate reports are market context and are not complete historical contract pricing."])

