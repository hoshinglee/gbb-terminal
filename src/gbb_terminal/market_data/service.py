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
            retrieved_at = datetime.now(timezone.utc)
            observation = pd.Timestamp(cached.index[-1]).to_pydatetime().replace(tzinfo=timezone.utc)
            self.history_cache[symbol] = cached
            self.updated_at[symbol] = retrieved_at
            self.metadata[symbol] = {
                "dataset": "daily_prices",
                "symbol": symbol,
                "source": "Yahoo Finance",
                "status": "Cached Snapshot",
                "knownAt": observation.isoformat(),
                "observationTimestamp": observation.isoformat(),
                "retrievedAt": retrieved_at.isoformat(),
                "qualityWarnings": ["Serving a fresh local DuckDB snapshot from a delayed public-data source."],
                "remainingQuota": None,
                "cached": True,
            }
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

    async def options(self, ticker: str, expiration: str | None = None) -> dict:
        symbol = ticker.upper().strip()
        cached = self.store.load_options(symbol, expiration=expiration)
        if cached is not None:
            return cached
        try:
            envelope = await asyncio.to_thread(self.yahoo.option_chain, symbol, expiration)
            payload = {**envelope.data, "source": envelope.source, "dataStatus": envelope.metadata(), "historicalStatus": "Current Snapshot"}
            self.store.save_options(symbol, payload)
            return payload
        except ProviderUnavailable as error:
            stale = self.store.load_options(symbol, expiration=expiration, max_age_minutes=None)
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

    async def _dashboard_row(self, symbol: str, name: str, period: str, benchmark_return: float | None = None) -> dict:
        try:
            history = await self.history(symbol, period)
            close = history["Close"].dropna()
            if len(close) < 2:
                raise ValueError(f"Not enough observations are available for {symbol}.")
            last, previous = float(close.iloc[-1]), float(close.iloc[-2])
            period_return = float(last / close.iloc[0] - 1)
            return {
                "symbol": symbol,
                "name": name,
                "price": round(last, 2),
                "change": round(last - previous, 2),
                "changePercent": round((last / previous - 1) * 100, 2),
                "periodReturn": round(period_return * 100, 2),
                "relativeStrength": round((period_return - benchmark_return) * 100, 2) if benchmark_return is not None else None,
                "dataStatus": self.metadata.get(symbol, {}),
                "available": True,
            }
        except ValueError as error:
            retrieved_at = datetime.now(timezone.utc).isoformat()
            return {
                "symbol": symbol,
                "name": name,
                "price": None,
                "change": None,
                "changePercent": None,
                "periodReturn": None,
                "relativeStrength": None,
                "dataStatus": {
                    "dataset": "daily_prices",
                    "symbol": symbol,
                    "source": "Yahoo Finance",
                    "status": "Unavailable",
                    "retrievedAt": retrieved_at,
                    "qualityWarnings": [str(error)],
                    "cached": False,
                },
                "available": False,
            }

    async def dashboard(self) -> dict:
        benchmark = await self._dashboard_row("SPY", "S&P 500 ETF", "3mo")
        benchmark_return = benchmark["periodReturn"] / 100 if benchmark["periodReturn"] is not None else None
        sector_rows = await asyncio.gather(*(
            self._dashboard_row(symbol, name, "3mo", benchmark_return)
            for symbol, name in SECTORS.items()
        ))
        macro_rows = await asyncio.gather(*(
            self._dashboard_row(symbol, name, "3mo")
            for symbol, name in MACRO.items()
        ))
        ordered_sectors = sorted(
            sector_rows,
            key=lambda row: (row["changePercent"] is not None, row["changePercent"] if row["changePercent"] is not None else float("-inf")),
            reverse=True,
        )
        return {"benchmark": benchmark, "sectors": ordered_sectors, "macro": macro_rows}
