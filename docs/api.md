# API Application

Source: `app/main.py`

## Business definition

The FastAPI application is the orchestration boundary for GBB Terminal. It accepts user requests, coordinates market data and strategies, and returns browser-ready JSON. It contains no strategy calculations itself.

## Main endpoints

| Endpoint | Function | Definition |
| --- | --- | --- |
| `POST /api/backtest` | `backtest` | Translate or load a strategy, fetch stock and SPY history, run it, and persist the result. |
| `POST /api/simulate` | `simulate` | Run bootstrap Monte Carlo paths from historical stock returns. |
| `GET /api/strategies` | `strategies` | Return the saved strategy catalogue, including YAML definitions. |
| `GET /api/llm/status` | `llm_status` | Report whether Google AI Studio is configured and which schema is used. |
| `GET /api/indicators` | `indicator_catalogue` | List indicators available to YAML strategies. |
| `GET /api/technical-indicators/{ticker}` | `technical_indicators` | Return OHLCV-derived indicator time series. |
| `GET /api/stock/{ticker}` | `stock` | Return price and volume observations for the stock dashboard. |
| `GET /api/options/{ticker}` | `options` | Return the nearest Yahoo Finance option chain. |

## Extension guidance

Keep endpoints thin. New calculations should live in a domain module and new persistence behavior should live in `storage.py`.
