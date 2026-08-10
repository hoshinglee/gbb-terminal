# GBB Terminal

GBB Terminal is a free, open-source research and simulation workbench for hobbyist US equity and options investors. It keeps underperformance visible, compares active ideas with passive benchmarks, and never sends brokerage orders.

## Current capabilities

- **Strategy Lab:** natural-language rules, validated templates, reusable strategy catalogue configurations, next-open execution, cost-aware backtests, fingerprinted research runs, SPY/automatic-sector/risk-matched benchmarks, walk-forward and Optuna parameter search, trade ledgers, multi-interval candlestick replay, and evidence verdicts.
- **Option Lab:** current Yahoo chain snapshots, American-option pricing, Greeks, price/time P&L surfaces, Monte Carlo paths, core single- and multi-leg positions, and an auditable paper lifecycle ledger.
- **Stock and Market:** OHLCV observability, current option open interest, sector performance, relative strength, and macro market proxies.
- **Company Intelligence:** canonical company IDs, point-in-time SEC facts, normalized financial history, historical trailing valuation, source-backed earnings events, session-aware reaction analytics, and an optional provider-neutral estimates boundary.
- **Local persistence:** DuckDB caches requested public data, company identities, strategies, research runs, option snapshots, paper positions, and lifecycle events.

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

Open `http://127.0.0.1:8000` for Strategy Lab, then use the shared navigation for Option Lab, Stock Observatory, Market Pulse, and Company Intelligence. Direct routes are `/?lab=options`, `/?lab=stock`, `/?lab=market`, and `/?lab=intelligence`; `ticker=NVDA` can be carried among company, stock, strategy, and option workflows. FastAPI serves the built React research application when `app/static/react/index.html` exists and otherwise falls back to the vanilla application. The migration fallback remains available at `http://127.0.0.1:8000/legacy`. Python commands work from any directory after editable installation because frontend, database, and log paths resolve through `gbb_terminal.settings`.

For frontend development, run `npm run dev` from `app/web`; Vite proxies `/api` requests to FastAPI on port 8000. Generated assets under `app/static/react/` are intentionally ignored and must be built in release or deployment workflows.

## Configuration

Copy `.env.example` to `.env`, then copy `conf/app.example.yaml` to ignored `conf/app.yaml`. Select Google AI Studio, OpenAI, or Anthropic Claude in `conf/app.yaml` and keep its API key only in `.env`. Without a configured provider, explicit built-in technical rules and risk controls still have a deterministic local translator. Provider output is constrained JSON, validated before use, and never becomes executable code. GBB Terminal never calls `eval` or `exec` on strategy input.

Runtime data belongs in ignored `data/` and `log/` directories. Existing `data/gbb_terminal.duckdb` files are migrated in place.

To populate the Release 0.7 company registry from the official SEC ticker/CIK directory, run `python scripts/sync_company_identities.py`. The SEC directory is current-association evidence, not a complete historical listing database; its limitations are persisted with the records.

After synchronizing one company's SEC facts with `python scripts/sync_company_facts.py NVDA`, open `/?lab=intelligence&ticker=NVDA` or inspect the V3 contracts under `/api/v3/companies/NVDA`. Financials, metrics, historical valuation, earnings reactions, and optional manual estimates remain separate from the existing V2 stock-market endpoint.

## Data and model limits

- Yahoo Finance data may be delayed, adjusted, incomplete, or unavailable.
- SEC filings become usable at acceptance time, not their report period.
- FINRA daily short-sale volume is not short interest.
- Free sources do not provide reliable historical contract-level option chains. Option Lab results are theoretical simulations initialized from current snapshots or manual inputs.
- Models omit taxes, broker-specific margin, market impact, pin risk, and full bid-ask depth.

Read [`docs/README.md`](docs/README.md) for architecture and module documentation. Contributions are accepted under the [Apache License 2.0](LICENSE); see [`CONTRIBUTING.md`](CONTRIBUTING.md).

Release readiness is tracked in [`docs/release-checklist.md`](docs/release-checklist.md). Launch-environment stability checks remain intentionally deferred until the application becomes a release candidate.
