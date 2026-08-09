# API Application

Sources: `src/gbb_terminal/api/main.py`, `src/gbb_terminal/api/routes/`, and `src/gbb_terminal/api/schemas/`

FastAPI is the orchestration boundary. Routes validate requests, call market/domain services, persist immutable records, and return browser-ready data. Calculation logic remains outside the route layer.

## V2 research endpoints

| Endpoint | Definition |
| --- | --- |
| `GET /api/v2/strategy-templates` | Return typed built-in templates and parameter metadata. |
| `POST /api/v2/strategy-proposals` | Translate natural language into a safe proposal and clarification list. |
| `POST /api/v2/strategies` | Validate and deduplicate a canonical `StrategyInstance`. |
| `POST /api/v2/research-runs` | Execute and persist an immutable, fingerprinted single-stock or ranked-portfolio run from a strategy configuration and `research_design`. |
| `GET /api/v2/research-runs/{id}` | Load one persisted run using the same snake-case ResearchRun contract returned at creation. |
| `POST /api/v2/parameter-searches` | Run exhaustive or seeded Optuna walk-forward search, evaluate an untouched final window, and persist the selected run. |
| `GET /api/v2/chart-data` | Return date-aligned OHLCV, indicators, and source metadata. |

## V2 observability endpoints

| Endpoint | Definition |
| --- | --- |
| `GET /api/v2/stocks/{ticker}?period=1y` | Return quote evidence and day/week/month/year OHLCV with technical indicators and provenance. |
| `GET /api/v2/market-overview` | Return SPY context, sector breadth inputs, three-month relative strength, cross-asset proxies, provider status, and generation time. |
| `GET /api/v2/data-providers` | Return configured free-provider adapter status. |
| `GET /api/v2/public-data/*` | Return SEC, FINRA, FRED, or OCC payloads with provider metadata and stale-cache fallback where available. |

Market overview rows are independently available or unavailable. A failed Yahoo symbol returns a visible row-level warning without discarding successful sector and macro rows. Fresh DuckDB price snapshots are labelled `Cached Snapshot`; they retain source, observation, known-at, retrieval, and quality-warning fields.

## V2 option endpoints

| Endpoint | Definition |
| --- | --- |
| `GET /api/v2/options/templates` | Return grouped Recipe V2 metadata, leg roles, and structural policies. |
| `GET /api/v2/options/chains/{ticker}?expiration=YYYY-MM-DD` | Return every provider-reported expiry and every contract for the selected current or cached expiry. |
| `POST /api/v2/options/simulations` | Calculate theoretical evidence and persist an immutable, versioned local simulation run. |
| `GET /api/v2/options/simulations` | List recent immutable simulation runs and their summary evidence. |
| `GET /api/v2/options/simulations/{id}` | Reload one exact simulation request and result. |
| `POST /api/v2/options/positions` | Create a paper-position ledger, optionally linked to its originating simulation run. |
| `GET /api/v2/options/positions` | List recently updated local paper positions for rediscovery after reload. |
| `GET /api/v2/options/positions/{id}` | Return current state and all earlier events. |
| `POST /api/v2/options/positions/{id}/events` | Apply and persist one validated lifecycle transition. |

Option-chain responses include the selected and default expiration, all available expirations, quote provenance, quote-quality warnings, and normalized bid/ask/last/mid/spread, volume, open interest, IV, moneyness, and last-trade fields. An unavailable requested expiry is rejected rather than silently replaced.

Legacy `/api/*` routes remain compatible during migration. `POST /api/strategy/propose` and its V2 counterpart validate provider-authored JSON, return clarification metadata, and expose only server-generated compatibility YAML to the existing backtest flow. Internal semantic keys and YAML are omitted from ordinary catalogue views; advanced export remains available through an intentional future workflow.

V2 request models reject unknown fields. `ResearchDesign` owns ticker/universe, benchmarks, timeframe, and execution assumptions; `StrategyInstance` owns only reusable rule and risk configuration. Relative-strength designs may resolve an automatic sector ETF from Yahoo sector metadata, or use an explicit custom symbol. Research-run responses include internal strategy and reproducibility keys for machine-level replay, but the browser intentionally does not display them in ordinary Strategy Lab views.

Individual-stock research results include an additive `marketChart` object. Its `intervals` map contains `day`, `week`, `month`, and `year` OHLCV points with interval-specific technical indicators and final strategy state for each bar. Ranked-portfolio results return `marketChart: null` because an average of different securities is not a valid tradable candlestick series. The existing `chart` equity-curve contract remains unchanged.

`request_logging_and_local_no_cache` records request IDs, duration, and status. Browser assets receive `Cache-Control: no-store`, preventing confusing conditional-cache responses during local development.
