# Architecture

## Business boundary

GBB Terminal is an educational research workbench, not an execution system, broker, adviser, or source of guaranteed returns. Stock Strategy Lab and Option Lab are independent domain products that share market data, storage, settings, and observability.

## Runtime layout

- `app/`: browser-only HTML, CSS, and JavaScript.
- `src/gbb_terminal/api/`: FastAPI application, schemas, and route groups.
- `src/gbb_terminal/strategy/`: strategy contracts, templates, safe factory, and indicators.
- `src/gbb_terminal/backtesting/`: signal execution, costs, metrics, Monte Carlo, parameter search, and portfolio ranking.
- `src/gbb_terminal/options/`: option contracts, American pricing, scenario simulation, strategy templates, and lifecycle transitions.
- `src/gbb_terminal/market_data/`: provider-neutral service and public provider adapters.
- `src/gbb_terminal/storage/`: DuckDB system of record.
- `src/gbb_terminal/llm/`: optional language-model translation only.
- `src/gbb_terminal/observability/`: application logging.
- `conf/`: checked-in configuration examples and ignored local runtime configuration.

`gbb_terminal.settings` resolves frontend, data, log, and configuration paths from the installed source location. `conf/app.yaml` holds non-secret local settings; `.env` holds secrets. Process environment variables and `.env` override YAML settings, so the server does not depend on its current working directory.

## Request flow

1. A route validates a Pydantic request.
2. Market data is loaded from a fresh DuckDB cache or a provider.
3. Provider failure falls back to stale local data when available and adds visible warnings.
4. A domain service calculates signals, research evidence, or an option state transition.
5. Immutable research or ledger records are persisted.
6. The API returns data plus assumptions and provenance for browser rendering.

Hosted authentication is intentionally absent. Storage tables allow nullable `owner_id` so repository logic can later support users without contaminating domain models.
