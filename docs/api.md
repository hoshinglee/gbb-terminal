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

## V2 option endpoints

| Endpoint | Definition |
| --- | --- |
| `GET /api/v2/options/chains/{ticker}` | Return the newest current or cached chain snapshot. |
| `POST /api/v2/options/simulations` | Calculate theoretical value, Greeks, surfaces, and Monte Carlo paths. |
| `POST /api/v2/options/positions` | Create a paper-position ledger. |
| `GET /api/v2/options/positions/{id}` | Return current state and all earlier events. |
| `POST /api/v2/options/positions/{id}/events` | Apply and persist one validated lifecycle transition. |

Legacy `/api/*` routes remain compatible during migration. Internal semantic keys and YAML are omitted from ordinary V2 catalogue responses; advanced export remains available in the browser.

V2 request models reject unknown fields. `ResearchDesign` owns ticker/universe, benchmarks, timeframe, and execution assumptions; `StrategyInstance` owns only reusable rule and risk configuration. Relative-strength designs may resolve an automatic sector ETF from Yahoo sector metadata, or use an explicit custom symbol. Research-run responses include internal strategy and reproducibility keys for machine-level replay, but the browser intentionally does not display them in ordinary Strategy Lab views.

Individual-stock research results include an additive `marketChart` object. Its `intervals` map contains `day`, `week`, `month`, and `year` OHLCV points with interval-specific technical indicators and final strategy state for each bar. Ranked-portfolio results return `marketChart: null` because an average of different securities is not a valid tradable candlestick series. The existing `chart` equity-curve contract remains unchanged.

`request_logging_and_local_no_cache` records request IDs, duration, and status. Browser assets receive `Cache-Control: no-store`, preventing confusing conditional-cache responses during local development.
