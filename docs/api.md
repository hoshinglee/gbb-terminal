# API Application

Sources: `src/gbb_terminal/api/main.py`, `src/gbb_terminal/api/routes/`, and `src/gbb_terminal/api/schemas/`

FastAPI is the orchestration boundary. Routes validate requests, call market/domain services, persist immutable records, and return browser-ready data. Calculation logic remains outside the route layer.

## V2 research endpoints

| Endpoint | Definition |
| --- | --- |
| `GET /api/v2/strategy-templates` | Return typed built-in templates and parameter metadata. |
| `POST /api/v2/strategy-proposals` | Translate natural language into a safe proposal and clarification list. |
| `POST /api/v2/strategies` | Validate and deduplicate a canonical `StrategyInstance`. |
| `POST /api/v2/research-runs` | Execute and persist an immutable single-stock or ranked-portfolio run. |
| `GET /api/v2/research-runs/{id}` | Load one persisted research run. |
| `POST /api/v2/parameter-searches` | Run guarded walk-forward search with an untouched final window. |
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

`request_logging_and_local_no_cache` records request IDs, duration, and status. Browser assets receive `Cache-Control: no-store`, preventing confusing conditional-cache responses during local development.
