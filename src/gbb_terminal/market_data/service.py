from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pandas as pd
from .providers import FINRAProvider, FREDProvider, OCCProvider, SECProvider, YahooProvider
from .providers.base import ProviderUnavailable
from ..storage.database import LocalMarketStore


SECTORS = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Health Care", "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples", "XLE": "Energy", "XLI": "Industrials", "XLB": "Materials",
    "XLU": "Utilities", "XLRE": "Real Estate", "XLC": "Communication Services",
}
SECTOR_ETFS = {
    "basic materials": "XLB",
    "communication services": "XLC",
    "consumer cyclical": "XLY",
    "consumer defensive": "XLP",
    "consumer discretionary": "XLY",
    "consumer staples": "XLP",
    "energy": "XLE",
    "financial services": "XLF",
    "financials": "XLF",
    "health care": "XLV",
    "healthcare": "XLV",
    "industrials": "XLI",
    "materials": "XLB",
    "real estate": "XLRE",
    "technology": "XLK",
    "utilities": "XLU",
}
MACRO = {"^GSPC": "S&P 500", "^VIX": "VIX", "DX-Y.NYB": "US Dollar", "GC=F": "Gold", "CL=F": "WTI Crude", "^TNX": "10Y Yield"}


class MarketData:
    def __init__(self, store: LocalMarketStore) -> None:
        self.store = store
        self.history_cache: dict[str, pd.DataFrame] = {}
        self.updated_at: dict[str, datetime] = {}
        self.metadata: dict[str, dict] = {}
        self.sector_benchmark_cache: dict[str, str | None] = {}
        self.yahoo = YahooProvider()
        self.sec = SECProvider()
        self.finra = FINRAProvider()
        self.fred = FREDProvider()
        self.occ = OCCProvider()
        self.providers = [self.yahoo, self.sec, self.finra, self.fred, self.occ]

    async def history(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        symbol = ticker.upper().strip()
        if not symbol.replace("-", "").replace("^", "").replace(".", "").replace("=", "").isalnum():
            raise ValueError("Ticker contains unsupported characters.")
        cached = self.store.load_history(symbol, period)
        if cached is not None:
            self.history_cache[symbol] = cached
            self.updated_at[symbol] = datetime.now(timezone.utc)
            return cached.copy()
        try:
            envelope = await asyncio.to_thread(self.yahoo.history, symbol, period)
            frame = envelope.data
            self.store.save_history(symbol, frame)
            self.metadata[symbol] = envelope.metadata()
        except ProviderUnavailable as error:
            frame = self.store.load_history(symbol, period, max_age_minutes=None)
            if frame is None:
                raise ValueError(str(error)) from error
            self.metadata[symbol] = {
                "dataset": "daily_prices", "symbol": symbol, "source": "Yahoo Finance",
                "status": "Stale Cache", "knownAt": frame.index[-1].isoformat(),
                "observationTimestamp": frame.index[-1].isoformat(), "retrievedAt": datetime.now(timezone.utc).isoformat(),
                "qualityWarnings": [str(error), "Serving the newest locally cached price history."], "cached": True,
            }
        self.history_cache[symbol] = frame
        self.updated_at[symbol] = datetime.now(timezone.utc)
        return frame.copy()

    async def quote(self, ticker: str) -> dict:
        history = await self.history(ticker, "1y")
        close = history["Close"].dropna()
        last, previous = float(close.iloc[-1]), float(close.iloc[-2])
        return {"symbol": ticker.upper(), "price": round(last, 2), "change": round(last - previous, 2), "changePercent": round((last / previous - 1) * 100, 2), "updatedAt": self.updated_at[ticker.upper()].isoformat(), "dataStatus": self.metadata.get(ticker.upper(), {})}

    async def options(self, ticker: str) -> dict:
        symbol = ticker.upper().strip()
        cached = self.store.load_options(symbol)
        if cached is not None:
            return cached
        try:
            envelope = await asyncio.to_thread(self.yahoo.option_chain, symbol)
            payload = {**envelope.data, "source": envelope.source, "dataStatus": envelope.metadata(), "historicalStatus": "Current Snapshot"}
            self.store.save_options(symbol, payload)
            return payload
        except ProviderUnavailable as error:
            stale = self.store.load_options(symbol, max_age_minutes=None)
            if stale is None:
                raise ValueError(str(error)) from error
            stale["dataStatus"] = {**stale.get("dataStatus", {}), "status": "Stale Cache", "qualityWarnings": [str(error), "Serving the newest locally cached option chain."]}
            return stale

    async def sector_benchmark(self, ticker: str) -> str | None:
        symbol = ticker.upper().strip()
        if symbol in self.sector_benchmark_cache:
            return self.sector_benchmark_cache[symbol]
        try:
            sector = await asyncio.to_thread(self.yahoo.sector, symbol)
        except ProviderUnavailable:
            self.sector_benchmark_cache[symbol] = None
            return None
        normalized = " ".join(sector.replace("_", " ").replace("-", " ").lower().split()) if sector else ""
        benchmark = SECTOR_ETFS.get(normalized)
        self.sector_benchmark_cache[symbol] = benchmark
        return benchmark

    def provider_statuses(self) -> list[dict]:
        return [provider.status() for provider in self.providers]

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
