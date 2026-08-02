from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from .storage import LocalMarketStore


SECTORS = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Health Care", "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples", "XLE": "Energy", "XLI": "Industrials", "XLB": "Materials",
    "XLU": "Utilities", "XLRE": "Real Estate", "XLC": "Communication Services",
}
MACRO = {"^GSPC": "S&P 500", "^VIX": "VIX", "DX-Y.NYB": "US Dollar", "GC=F": "Gold", "CL=F": "WTI Crude", "^TNX": "10Y Yield"}


class MarketData:
    def __init__(self, store: LocalMarketStore) -> None:
        self.store = store
        self.history_cache: dict[str, pd.DataFrame] = {}
        self.updated_at: dict[str, datetime] = {}

    async def history(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        symbol = ticker.upper().strip()
        if not symbol.replace("-", "").replace("^", "").replace(".", "").replace("=", "").isalnum():
            raise ValueError("Ticker contains unsupported characters.")
        cached = self.store.load_history(symbol, period)
        if cached is not None:
            self.history_cache[symbol] = cached
            self.updated_at[symbol] = datetime.now(timezone.utc)
            return cached.copy()
        frame = await asyncio.to_thread(yf.Ticker(symbol).history, period=period, auto_adjust=True)
        if frame.empty or "Close" not in frame:
            raise ValueError(f"No Yahoo Finance price data found for {symbol}.")
        frame.index = pd.to_datetime(frame.index).tz_localize(None)
        self.store.save_history(symbol, frame)
        self.history_cache[symbol] = frame
        self.updated_at[symbol] = datetime.now(timezone.utc)
        return frame.copy()

    async def quote(self, ticker: str) -> dict:
        history = await self.history(ticker, "1y")
        close = history["Close"].dropna()
        last, previous = float(close.iloc[-1]), float(close.iloc[-2])
        return {"symbol": ticker.upper(), "price": round(last, 2), "change": round(last - previous, 2), "changePercent": round((last / previous - 1) * 100, 2), "updatedAt": self.updated_at[ticker.upper()].isoformat()}

    async def options(self, ticker: str) -> dict:
        symbol = ticker.upper().strip()
        cached = self.store.load_options(symbol)
        if cached is not None:
            return cached
        stock = yf.Ticker(symbol)
        expirations = await asyncio.to_thread(lambda: list(stock.options))
        if not expirations:
            return {"expirations": [], "calls": [], "puts": []}
        expiry = expirations[0]
        chain = await asyncio.to_thread(stock.option_chain, expiry)
        def number(value: object) -> float:
            return 0.0 if pd.isna(value) else float(value)
        def rows(frame: pd.DataFrame) -> list[dict]:
            return [{"contract": row.contractSymbol, "strike": number(row.strike), "last": number(row.lastPrice), "bid": number(row.bid), "ask": number(row.ask), "volume": int(number(row.volume)), "openInterest": int(number(row.openInterest)), "iv": round(number(row.impliedVolatility) * 100, 1)} for row in frame.head(12).itertuples()]
        payload = {"expiration": expiry, "expirations": expirations[:8], "calls": rows(chain.calls), "puts": rows(chain.puts)}
        self.store.save_options(symbol, payload)
        return payload

    async def dashboard(self) -> dict:
        sector_quotes = await asyncio.gather(*(self.quote(symbol) for symbol in SECTORS))
        sector_rows = [{"symbol": symbol, "name": SECTORS[symbol], **quote} for symbol, quote in zip(SECTORS, sector_quotes)]
        spy = await self.history("SPY", "3mo")
        spy_return = spy.Close.iloc[-1] / spy.Close.iloc[0] - 1
        macro_quotes = await asyncio.gather(*(self.quote(symbol) for symbol in MACRO))
        macro_rows = [{"name": MACRO[symbol], **quote} for symbol, quote in zip(MACRO, macro_quotes)]
        sector_history = await asyncio.gather(*(self.history(row["symbol"], "3mo") for row in sector_rows))
        for row, series in zip(sector_rows, sector_history):
            row["relativeStrength"] = round(((series.Close.iloc[-1] / series.Close.iloc[0] - 1) - spy_return) * 100, 2)
        return {"sectors": sorted(sector_rows, key=lambda row: row["changePercent"], reverse=True), "macro": macro_rows}
