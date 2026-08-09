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

    def option_chain(self, symbol: str, expiration: str | None = None) -> DataEnvelope[dict]:
        stock = yf.Ticker(symbol)
        expirations = list(stock.options)
        retrieved_at = datetime.now(timezone.utc)
        if not expirations:
            return DataEnvelope("current_option_chain", symbol, {"expirations": [], "calls": [], "puts": []}, retrieved_at, retrieved_at, retrieved_at, self.delayed_status, self.name, ["No current contracts were returned."])
        expiry = expiration or expirations[0]
        if expiry not in expirations:
            raise ProviderUnavailable(f"Yahoo Finance does not currently list {expiry} as an option expiration for {symbol}.")
        chain = stock.option_chain(expiry)

        def number(value: object) -> float:
            return 0.0 if pd.isna(value) else float(value)

        def timestamp(value: object) -> str | None:
            if value is None or pd.isna(value):
                return None
            parsed = pd.Timestamp(value)
            return parsed.isoformat()

        def rows(frame: pd.DataFrame) -> list[dict]:
            contracts = []
            for row in frame.itertuples():
                bid = number(getattr(row, "bid", 0))
                ask = number(getattr(row, "ask", 0))
                contracts.append({
                    "contract": row.contractSymbol,
                    "strike": number(row.strike),
                    "last": number(row.lastPrice),
                    "bid": bid,
                    "ask": ask,
                    "mid": round((bid + ask) / 2, 4) if bid > 0 and ask > 0 else 0.0,
                    "spread": round(max(ask - bid, 0), 4),
                    "change": number(getattr(row, "change", 0)),
                    "percentChange": number(getattr(row, "percentChange", 0)),
                    "volume": int(number(getattr(row, "volume", 0))),
                    "openInterest": int(number(getattr(row, "openInterest", 0))),
                    "iv": round(number(getattr(row, "impliedVolatility", 0)) * 100, 2),
                    "inTheMoney": bool(getattr(row, "inTheMoney", False)),
                    "lastTradeAt": timestamp(getattr(row, "lastTradeDate", None)),
                    "currency": str(getattr(row, "currency", "USD") or "USD"),
                    "quoteQuality": "Two-Sided" if bid > 0 and ask > 0 else "Incomplete Quote",
                })
            return contracts

        payload = {"expiration": expiry, "defaultExpiration": expirations[0], "expirations": expirations, "calls": rows(chain.calls), "puts": rows(chain.puts)}
        return DataEnvelope("current_option_chain", symbol, payload, retrieved_at, retrieved_at, retrieved_at, self.delayed_status, self.name, ["This snapshot is current-chain data, not a historical option backtest dataset."])

    def sector(self, symbol: str) -> str | None:
        try:
            info = yf.Ticker(symbol).get_info()
        except Exception as error:
            raise ProviderUnavailable(f"Yahoo Finance sector metadata is unavailable for {symbol}.") from error
        value = info.get("sectorKey") or info.get("sector")
        return str(value).strip() if value else None
