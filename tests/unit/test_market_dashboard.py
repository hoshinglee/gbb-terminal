import asyncio

import pandas as pd

from gbb_terminal.market_data.service import MarketData
from gbb_terminal.storage.database import LocalMarketStore


def test_market_dashboard_keeps_available_rows_when_one_symbol_fails(tmp_path):
    data = MarketData(LocalMarketStore(tmp_path / "dashboard.duckdb"))

    async def history(ticker, period):
        if ticker == "XLE":
            raise ValueError("Fixture provider outage")
        index = pd.date_range("2026-01-02", periods=80, freq="B")
        close = pd.Series(range(100, 180), index=index, dtype=float)
        data.metadata[ticker] = {"source": "Fixture", "status": "Delayed", "knownAt": index[-1].isoformat()}
        return pd.DataFrame({"Open": close - 1, "High": close + 1, "Low": close - 2, "Close": close, "Volume": 1_000_000}, index=index)

    data.history = history
    dashboard = asyncio.run(data.dashboard())

    energy = next(row for row in dashboard["sectors"] if row["symbol"] == "XLE")
    technology = next(row for row in dashboard["sectors"] if row["symbol"] == "XLK")
    assert energy["available"] is False
    assert energy["dataStatus"]["status"] == "Unavailable"
    assert "Fixture provider outage" in energy["dataStatus"]["qualityWarnings"][0]
    assert technology["available"] is True
    assert technology["relativeStrength"] == 0
