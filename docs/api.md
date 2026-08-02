# API Application

Source: `app/main.py`

## Business definition

The FastAPI application is the orchestration boundary for GBB Terminal. It accepts user requests, coordinates market data and strategies, and returns browser-ready JSON. It contains no strategy calculations itself.

## Main endpoints

| Endpoint | Function | Definition |
| --- | --- | --- |
| `POST /api/strategy/propose` | `propose_strategy` | Translate an instruction and return normalized, validated YAML plus assumptions and duplicate status for user confirmation. |
| `POST /api/backtest` | `backtest` | Translate or load a strategy, fetch stock and SPY history, run it, and persist the result. |
| `POST /api/simulate` | `simulate` | Run bootstrap Monte Carlo paths from historical stock returns. |
| `GET /api/strategies` | `strategies` | Return the saved strategy catalogue, including YAML definitions. |
| `GET /api/llm/status` | `llm_status` | Report whether Google AI Studio is configured and which schema is used. |
| `GET /api/indicators` | `indicator_catalogue` | List indicators available to YAML strategies. |
| `GET /api/technical-indicators/{ticker}` | `technical_indicators` | Return OHLCV-derived indicator time series. |
| `GET /api/stock/{ticker}` | `stock` | Return price and volume observations for the stock dashboard. |
| `GET /api/options/{ticker}` | `options` | Return the nearest Yahoo Finance option chain. |

## Confirmed strategy flow

`POST /api/strategy/propose` does not persist or execute a new strategy. The browser first presents the generated name, business description, clarifications, semantic key, and YAML. After user confirmation, `POST /api/backtest` receives the validated YAML in `strategy_yaml`, recomputes its semantic key server-side, saves or reuses the catalogue record, and runs the test.

Catalogue-loaded strategies use `strategy_id` and bypass translation. Legacy clients can still submit only `instruction`, in which case the backtest endpoint translates and validates it server-side.

## Request middleware

`request_logging_and_local_no_cache` assigns a request ID, records duration and status, and applies `Cache-Control: no-store` to `/` and `/static/*`. It removes conditional cache headers for those local assets so browser refreshes return `200` rather than repetitive `304 Not Modified` access-log entries during development.

## Extension guidance

Keep endpoints thin. New calculations should live in a domain module and new persistence behavior should live in `storage.py`.
