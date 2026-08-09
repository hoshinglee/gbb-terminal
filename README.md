# GBB Terminal

GBB Terminal is a free, open-source research and simulation workbench for hobbyist US equity and options investors. It keeps underperformance visible, compares active ideas with passive benchmarks, and never sends brokerage orders.

## Current capabilities

- **Strategy Lab:** natural-language rules, validated templates, reusable strategy catalogue configurations, next-open execution, cost-aware backtests, fingerprinted research runs, SPY/automatic-sector/risk-matched benchmarks, walk-forward and Optuna parameter search, trade ledgers, multi-interval candlestick replay, and evidence verdicts.
- **Option Lab:** current Yahoo chain snapshots, American-option pricing, Greeks, price/time P&L surfaces, Monte Carlo paths, core single- and multi-leg positions, and an auditable paper lifecycle ledger.
- **Stock and Market:** OHLCV observability, current option open interest, sector performance, relative strength, and macro market proxies.
- **Local persistence:** DuckDB caches requested public data, strategies, research runs, option snapshots, paper positions, and lifecycle events.

## Run locally

Python 3.11 or newer and a Vite-compatible Node.js runtime are required for the React interface.

```bash
conda activate gbbterminal
pip install -e ".[dev]"
cd app/web
npm install
npm run build
cd ../..
uvicorn gbb_terminal.api.main:app --reload
```

Open `http://127.0.0.1:8000` for Strategy Lab and `http://127.0.0.1:8000/?lab=options` for Option Lab. FastAPI serves the built React research application when `app/static/react/index.html` exists and otherwise falls back to the vanilla application. The legacy interface remains available at `http://127.0.0.1:8000/legacy`. Python commands work from any directory after editable installation because frontend, database, and log paths resolve through `gbb_terminal.settings`.

For frontend development, run `npm run dev` from `app/web`; Vite proxies `/api` requests to FastAPI on port 8000. Generated assets under `app/static/react/` are intentionally ignored and must be built in release or deployment workflows.

## Configuration

Copy `.env.example` to `.env`, then copy `conf/app.example.yaml` to ignored `conf/app.yaml`. Select Google AI Studio, OpenAI, or Anthropic Claude in `conf/app.yaml` and keep its API key only in `.env`. Without a configured provider, explicit built-in technical rules and risk controls still have a deterministic local translator. Provider output is constrained JSON, validated before use, and never becomes executable code. GBB Terminal never calls `eval` or `exec` on strategy input.

Runtime data belongs in ignored `data/` and `log/` directories. Existing `data/gbb_terminal.duckdb` files are migrated in place.

## Data and model limits

- Yahoo Finance data may be delayed, adjusted, incomplete, or unavailable.
- SEC filings become usable at acceptance time, not their report period.
- FINRA daily short-sale volume is not short interest.
- Free sources do not provide reliable historical contract-level option chains. Option Lab results are theoretical simulations initialized from current snapshots or manual inputs.
- Models omit taxes, broker-specific margin, market impact, pin risk, and full bid-ask depth.

Read [`docs/README.md`](docs/README.md) for architecture and module documentation. Contributions are accepted under the [Apache License 2.0](LICENSE); see [`CONTRIBUTING.md`](CONTRIBUTING.md).

Release readiness is tracked in [`docs/release-checklist.md`](docs/release-checklist.md). Launch-environment stability checks remain intentionally deferred until the application becomes a release candidate.
