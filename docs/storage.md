# DuckDB Storage

Source: `src/gbb_terminal/storage/database.py`

DuckDB is the local system of record and analytical cache. `LocalMarketStore` creates missing tables and adds backward-compatible columns without deleting existing `data/gbb_terminal.duckdb` records.

| Table | Purpose |
| --- | --- |
| `price_history` | Cached daily OHLCV by symbol and observation date. |
| `option_chains` | Latest normalized chain for fast loading. |
| `option_chain_snapshots` | One current-chain snapshot per symbol, expiry, and local day. |
| `provider_cache` | Public-data payload plus observation, known-at, and retrieval metadata. |
| `strategy_catalogue` | Canonical JSON/legacy YAML, family, template version, and hidden semantic key. |
| `backtest_runs`, `backtest_trades` | Legacy run summaries and closed trade records. |
| `research_runs` | Immutable Strategy V2, data snapshot, validation, tested settings, and results. |
| `option_positions` | Current complete paper-position state with nullable future `owner_id`. |
| `option_position_events` | Append-only lifecycle event payload and state-after snapshot. |
| `local_jobs` | Replaceable local progress/cancellation storage for long research work. |

`save_strategy()` updates an existing semantic identity instead of creating a duplicate. V2 strategy identity includes the template version, parameter values, and risk definition; it excludes ticker, universe, benchmark, timeframe, execution assumptions, display name, and description. Those research inputs live in `research_design` and contribute to the separate research-run reproducibility key. Keys remain internal because they are reproducibility metadata, not user decisions.

Every option event is written transactionally with the resulting position state. The ledger can therefore reconcile premium cash, shares, contracts, collateral, and realized P&L after close, roll, exercise, expiry, or assignment.

Runtime `data/` is excluded from Git.

See [System Diagrams](system-diagrams.md) for the logical DuckDB entity-relationship view and the provider-cache request sequence.
