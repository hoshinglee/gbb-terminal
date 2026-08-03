# Market Data

Source: `app/market_data.py`

## Business definition

The market-data module provides delayed US-market research data for stocks, options, sector ETFs, and macro proxies. Yahoo Finance is an MVP provider and should not be treated as an execution-grade feed.

## Functions

| Name | Definition |
| --- | --- |
| `MarketData.history` | Validate a symbol, use fresh DuckDB data when available, or download OHLCV history. |
| `MarketData.quote` | Derive last price and daily change from history. |
| `MarketData.options` | Retrieve and normalize the nearest option chain. |
| `MarketData.dashboard` | Build sector relative strength and macro snapshots. |

OHLCV means open, high, low, close, and volume. Volume is persisted with every price-history request and is available to the indicator registry.
