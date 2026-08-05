# Market Data

Sources: `src/gbb_terminal/market_data/service.py` and `src/gbb_terminal/market_data/providers/`

## Business definition

The market-data module provides delayed US-market research data for stocks, options, sector ETFs, and macro proxies. Yahoo Finance is an MVP provider and should not be treated as an execution-grade feed.

## Functions

| Name | Definition |
| --- | --- |
| `MarketData.history` | Validate a symbol, use fresh DuckDB data when available, or download OHLCV history. |
| `MarketData.quote` | Derive last price and daily change from history. |
| `MarketData.options` | Retrieve and normalize a current option chain, then preserve a daily snapshot. |
| `MarketData.dashboard` | Build sector relative strength and macro snapshots. |
| `MarketData.provider_statuses` | Describe available Yahoo, SEC, FINRA, FRED, and OCC adapters. |

OHLCV means open, high, low, close, and volume. Volume is persisted with every price-history request and is available to the indicator registry.

Provider results use `DataEnvelope` metadata. A failed provider request falls back to stale DuckDB data when possible and includes a visible quality warning.
