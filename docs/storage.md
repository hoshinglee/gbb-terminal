# DuckDB Storage

Source: `src/gbb_terminal/storage/database.py`

DuckDB is the local system of record and analytical cache. `LocalMarketStore` creates missing tables and adds backward-compatible columns without deleting existing `data/gbb_terminal.duckdb` records.

| Table | Purpose |
| --- | --- |
| `price_history` | Cached daily OHLCV by symbol and observation date. |
| `option_chains` | Latest normalized chain for fast loading. |
| `option_chain_snapshots` | One current-chain snapshot per symbol, expiry, and local day. |
| `option_simulation_runs` | Immutable validated request, complete result, provenance, model version, and creation time for every Option Lab run. |
| `provider_cache` | Public-data payload plus observation, known-at, and retrieval metadata. |
| `companies` | Durable company identity keyed by `company_id`, with unique normalized CIK and latest metadata provenance. |
| `company_security_mappings` | Time-bounded ticker/exchange mappings, primary-security state, and mapping-level provenance. |
| `strategy_catalogue` | Canonical JSON/legacy YAML, family, template version, and hidden semantic key. |
| `backtest_runs`, `backtest_trades` | Legacy run summaries and closed trade records. |
| `research_runs` | Immutable Strategy V2, data snapshot, validation, tested settings, and results. |
| `option_positions` | Current complete paper-position state with nullable future `owner_id`. |
| `option_position_events` | Append-only lifecycle event payload and state-after snapshot. |
| `local_jobs` | Replaceable local progress/cancellation storage for long research work. |

`save_strategy()` updates an existing semantic identity instead of creating a duplicate. V2 strategy identity includes the template version, parameter values, and risk definition; it excludes ticker, universe, benchmark, timeframe, execution assumptions, display name, and description. Those research inputs live in `research_design` and contribute to the separate research-run reproducibility key. Keys remain internal because they are reproducibility metadata, not user decisions.

Every requested ticker/expiry chain is cached independently. Loading a later expiry never replaces the symbol's default nearest-expiry cache. Every option simulation is append-only and may be reloaded independently of a paper position. Paper positions optionally store `research_run_id`, and every lifecycle event is written transactionally with the resulting position state. The ledger can therefore reconcile premium cash, signed shares, share basis, contracts, collateral, realized P&L, and current structure after close, roll, share trade, added leg, exercise, expiry, or assignment.

Company identity is independent of market-data symbol caches. `companies` retains the durable business key and `company_security_mappings` appends dated ticker/exchange associations. Duplicate CIK registration updates the existing company, active ticker conflicts are rejected, and ticker changes or delistings close mappings rather than deleting them. Schema version 6 creates these tables without rewriting existing price, strategy, option, or provider records.

Runtime `data/` is excluded from Git.

See [System Diagrams](system-diagrams.md) for the logical DuckDB entity-relationship view and the provider-cache request sequence.
