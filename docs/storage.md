# DuckDB Storage

Source: `app/storage.py`

## Business definition

DuckDB makes the local MVP responsive and reproducible. It stores downloaded data, strategy definitions, backtest summaries, and trade records without requiring a separate database service.

## Tables

| Table | Purpose |
| --- | --- |
| `price_history` | Cached OHLCV history by symbol and date. |
| `option_chains` | Cached normalized option-chain JSON. |
| `strategy_catalogue` | Natural-language instruction, metadata, provider, and canonical YAML. |
| `backtest_runs` | Ticker, window, metrics, and strategy used for a run. |
| `backtest_trades` | Entry, exit, side, absolute P&L, and percentage P&L. |

## Main functions

- `save_history` / `load_history` manage the market cache.
- `save_options` / `load_options` manage option-chain cache.
- `save_strategy`, `list_strategies`, and `get_strategy` manage loadable catalogue items.
- `save_backtest` persists run-level metrics and closed trades.

The database lives at `data/gbb_terminal.duckdb` and is excluded from Git.
