# GBB Terminal

GBB Terminal is a free, open-source research and simulation workbench for hobbyist US equity and options investors. It keeps underperformance visible, compares active ideas with passive benchmarks, and never sends brokerage orders.

## Current capabilities

- **Strategy Lab:** natural-language rules, validated templates, next-open execution, cost-aware backtests, fingerprinted research runs, SPY/sector/peer/risk-matched benchmarks, walk-forward and Optuna parameter search, trade ledgers, evidence verdicts, and Monte Carlo paths.
- **Option Lab:** current Yahoo chain snapshots, American-option pricing, Greeks, price/time P&L surfaces, Monte Carlo paths, core single- and multi-leg positions, and an auditable paper lifecycle ledger.
- **Stock and Market:** OHLCV observability, current option open interest, sector performance, relative strength, and macro market proxies.
- **Local persistence:** DuckDB caches requested public data, strategies, research runs, option snapshots, paper positions, and lifecycle events.

## Run locally

Python 3.11 or newer is required.

```bash
conda activate gbbterminal
pip install -e ".[dev]"
uvicorn gbb_terminal.api.main:app --reload
```

Open `http://127.0.0.1:8000`. The command works from any directory after editable installation because frontend, database, and log paths resolve through `gbb_terminal.settings`.

## Configuration

Copy `.env.example` to `.env`, then copy `conf/app.example.yaml` to ignored `conf/app.yaml`. Select Google AI Studio, OpenAI, or Anthropic Claude in `conf/app.yaml` and keep its API key only in `.env`. Without a configured provider, a deterministic moving-average parser remains available. External instructions are interpreted only through a constrained strategy schema. GBB Terminal never calls `eval` or `exec` on strategy input.

Runtime data belongs in ignored `data/` and `log/` directories. Existing `data/gbb_terminal.duckdb` files are migrated in place.

## Data and model limits

- Yahoo Finance data may be delayed, adjusted, incomplete, or unavailable.
- SEC filings become usable at acceptance time, not their report period.
- FINRA daily short-sale volume is not short interest.
- Free sources do not provide reliable historical contract-level option chains. Option Lab results are theoretical simulations initialized from current snapshots or manual inputs.
- Models omit taxes, broker-specific margin, market impact, pin risk, and full bid-ask depth.

Read [`docs/README.md`](docs/README.md) for architecture and module documentation. Contributions are accepted under the [Apache License 2.0](LICENSE); see [`CONTRIBUTING.md`](CONTRIBUTING.md).

Release readiness is tracked in [`docs/release-checklist.md`](docs/release-checklist.md). Launch-environment stability checks remain intentionally deferred until the application becomes a release candidate.
