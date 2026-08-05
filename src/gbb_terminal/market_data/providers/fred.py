from __future__ import annotations

import io
from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd

from ..models import DataEnvelope
from .base import BaseProvider


class FREDProvider(BaseProvider):
    name = "Federal Reserve Economic Data"

    def series(self, series_id: str) -> DataEnvelope[pd.DataFrame]:
        normalized = series_id.upper().strip()
        raw = self.request_bytes(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={quote(normalized)}")
        frame = pd.read_csv(io.BytesIO(raw))
        if frame.empty:
            raise ValueError(f"No FRED observations found for {normalized}.")
        if "DATE" not in frame and "observation_date" in frame:
            frame = frame.rename(columns={"observation_date": "DATE"})
        frame["DATE"] = pd.to_datetime(frame["DATE"])
        observation = frame["DATE"].iloc[-1].to_pydatetime().replace(tzinfo=timezone.utc)
        retrieved_at = datetime.now(timezone.utc)
        return DataEnvelope("macro_series", normalized, frame, observation, retrieved_at, retrieved_at, self.delayed_status, self.name, ["FRED series have different release schedules and may be revised."])
