# GBB Terminal

GBB Terminal is a free, open-source research and simulation workbench for hobbyist US equity and options investors. It keeps underperformance visible, compares active ideas with passive benchmarks, and never sends brokerage orders.

## Current capabilities

- **Strategy Lab:** natural-language rules, validated templates, reusable strategy catalogue configurations, next-open execution, cost-aware backtests, fingerprinted research runs, SPY/automatic-sector/risk-matched benchmarks, walk-forward and Optuna parameter search, trade ledgers, multi-interval candlestick replay, and evidence verdicts.
- **Option Lab:** outlook-led structure comparison, server-priced future price/date scenarios, current Yahoo chain snapshots, American-option pricing, Greeks, price/time P&L surfaces, core single- and multi-leg positions, and an optional auditable paper lifecycle ledger.
- **Market Pulse:** sector performance, relative strength, macro market proxies, provider-health context, and selectable current S&P 500 constituent research with market-cap treemaps and daily movers.
- **Company Intelligence:** the canonical stock-research experience with current quote context, a browser-local watchlist, complete annual/quarterly/TTM history, historical valuation regimes, event-focused candlesticks, source-backed earnings and business evidence, and cancellable SEC filing ingestion.
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

Open `http://127.0.0.1:8000` for Strategy Lab, then use the shared navigation for Option Lab, Market Pulse, and Company Intelligence. Direct routes are `/?lab=options`, `/?lab=market`, and `/?lab=intelligence`; `ticker=NVDA` carries a symbol among company, strategy, and option workflows. Old `/?lab=stock&ticker=...` links preserve the ticker and canonicalize to Company Intelligence. FastAPI serves the built React research application when `app/static/react/index.html` exists and otherwise falls back to the vanilla application. The migration fallback remains available at `http://127.0.0.1:8000/legacy`. Python commands work from any directory after editable installation because frontend, database, and log paths resolve through `gbb_terminal.settings`.

For frontend development, run `npm run dev` from `app/web`; Vite proxies `/api` requests to FastAPI on port 8000. Generated assets under `app/static/react/` are intentionally ignored and must be built in release or deployment workflows.

## Configuration

Copy `.env.example` to `.env`, then copy `conf/app.example.yaml` to ignored `conf/app.yaml`. Select Google AI Studio, OpenAI, or Anthropic Claude in `conf/app.yaml` and keep its API key only in `.env`. Without a configured provider, explicit built-in technical rules and risk controls still have a deterministic local translator. Provider output is constrained JSON, validated before use, and never becomes executable code. GBB Terminal never calls `eval` or `exec` on strategy input.

Runtime data belongs in ignored `data/` and `log/` directories. Existing `data/gbb_terminal.duckdb` files are migrated in place.

To populate the Release 0.7 company registry from the official SEC ticker/CIK directory, run `python scripts/sync_company_identities.py`. The SEC directory is current-association evidence, not a complete historical listing database; its limitations are persisted with the records.

After synchronizing one company's SEC facts with `python scripts/sync_company_facts.py NVDA`, open `/?lab=intelligence&ticker=NVDA` or inspect the V3 contracts under `/api/v3/companies/NVDA`. Financials, metrics, historical valuation, earnings reactions, and optional manual estimates remain separate from the existing V2 stock-market endpoint.

Refresh permitted filing documents for Network, Operations, Guidance, and Sources from the Company Intelligence **Sources** tab or the local CLI:

```bash
gbb-terminal intelligence refresh NVDA
gbb-terminal intelligence health NVDA
```

Download or resume the current S&P 500 personal-research cache from Market Pulse or the CLI:

```bash
gbb-terminal universe refresh sp500
gbb-terminal universe status sp500
```

The initial public membership source is a current Wikipedia snapshot, not licensed historical S&P index membership. A complete refresh can take substantial time and is designed to preserve partial progress, skip fresh companies, and resume safely.

## Data and model limits

- Yahoo Finance data may be delayed, adjusted, incomplete, or unavailable.
- The public S&P 500 constituent source represents current composition when retrieved and must not be used as historical-membership evidence in backtests.
- SEC filings become usable at acceptance time, not their report period.
- FINRA daily short-sale volume is not short interest.
- Free sources do not provide reliable historical contract-level option chains. Option Lab results are theoretical simulations initialized from current snapshots or manual inputs.
- Models omit taxes, broker-specific margin, market impact, pin risk, and full bid-ask depth.

Read [`docs/README.md`](docs/README.md) for architecture and module documentation. Contributions are accepted under the [Apache License 2.0](LICENSE); see [`CONTRIBUTING.md`](CONTRIBUTING.md).

Release readiness is tracked in [`docs/release-checklist.md`](docs/release-checklist.md). Launch-environment stability checks remain intentionally deferred until the application becomes a release candidate.
