from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from ..models import DataEnvelope
from .base import BaseProvider, ProviderUnavailable


class YahooProvider(BaseProvider):
    name = "Yahoo Finance"

    def history(self, symbol: str, period: str) -> DataEnvelope[pd.DataFrame]:
        frame = yf.Ticker(symbol).history(period=period, auto_adjust=True)
        if frame.empty or "Close" not in frame:
            raise ProviderUnavailable(f"No Yahoo Finance price data found for {symbol}.")
        frame.index = pd.to_datetime(frame.index).tz_localize(None)
        retrieved_at = datetime.now(timezone.utc)
        observation = frame.index[-1].to_pydatetime().replace(tzinfo=timezone.utc)
        return DataEnvelope("daily_prices", symbol, frame, observation, observation, retrieved_at, self.delayed_status, self.name, ["Free Yahoo data may be delayed or adjusted after publication."])

    def option_chain(self, symbol: str) -> DataEnvelope[dict]:
        stock = yf.Ticker(symbol)
        expirations = list(stock.options)
        retrieved_at = datetime.now(timezone.utc)
        if not expirations:
            return DataEnvelope("current_option_chain", symbol, {"expirations": [], "calls": [], "puts": []}, retrieved_at, retrieved_at, retrieved_at, self.delayed_status, self.name, ["No current contracts were returned."])
        expiry = expirations[0]
        chain = stock.option_chain(expiry)

        def number(value: object) -> float:
            return 0.0 if pd.isna(value) else float(value)

        def rows(frame: pd.DataFrame) -> list[dict]:
            return [{"contract": row.contractSymbol, "strike": number(row.strike), "last": number(row.lastPrice), "bid": number(row.bid), "ask": number(row.ask), "volume": int(number(row.volume)), "openInterest": int(number(row.openInterest)), "iv": round(number(row.impliedVolatility) * 100, 1)} for row in frame.itertuples()]

        payload = {"expiration": expiry, "expirations": expirations, "calls": rows(chain.calls), "puts": rows(chain.puts)}
        return DataEnvelope("current_option_chain", symbol, payload, retrieved_at, retrieved_at, retrieved_at, self.delayed_status, self.name, ["This snapshot is current-chain data, not a historical option backtest dataset."])

