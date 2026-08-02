# DuckDB Storage

Source: `app/storage.py`

## Business definition

DuckDB makes the local MVP responsive and reproducible. It stores downloaded data, strategy definitions, backtest summaries, and trade records without requiring a separate database service.

## Tables

| Table | Purpose |
| --- | --- |
| `price_history` | Cached OHLCV history by symbol and date. |
| `option_chains` | Cached normalized option-chain JSON. |
| `strategy_catalogue` | Natural-language instruction, normalized metadata, provider, canonical YAML, and semantic `strategy_key`. |
| `backtest_runs` | Ticker, window, metrics, and strategy used for a run. |
| `backtest_trades` | Entry, exit, side, absolute P&L, and percentage P&L. |

## Main functions

- `save_history` / `load_history` manage the market cache.
- `save_options` / `load_options` manage option-chain cache.
- `save_strategy`, `list_strategies`, and `get_strategy` manage loadable catalogue items.
- `deduplicate_strategies` migrates existing rows to canonical keys, redirects historical runs to the newest equivalent definition, and removes duplicate catalogue rows transactionally.
- `save_backtest` persists run-level metrics and closed trades.

## Strategy identity

`strategy_key` is a SHA-256 digest of executable strategy meaning: direction, normalized indicators, entry/exit rules, optional right-side multipliers, and risk settings. Names, descriptions, original wording, provider, YAML aliases, and formatting are excluded. Equivalent instructions therefore update and reuse one catalogue item instead of creating duplicates.

Open positions are returned to the browser as mark-to-market ledger rows but are not inserted into `backtest_trades`, whose schema requires a final exit date. Closed positions remain durable audit records.

The database lives at `data/gbb_terminal.duckdb` and is excluded from Git.
