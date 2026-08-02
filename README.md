# GBB Terminal

A local-first US-market financial terminal MVP. It prioritizes natural-language moving-average strategies, backtesting, and Monte Carlo analysis, then adds stock/options and sector/macro observability.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Google AI Studio

1. Copy `.env.example` to `.env` if it is not already present.
2. Add your Google AI Studio key as `GEMINI_API_KEY`.
3. Restart the server and run a Strategy Lab backtest.

Without a key, the application uses its deterministic moving-average parser. With a key, Google AI Studio translates the instruction into the same validated strategy schema before it reaches the strategy factory.

## Notes

- Data is sourced from Yahoo Finance and may be delayed, incomplete, or unavailable. It is for research only, not trading advice.
- Requested price history and option chains are stored locally in `data/gbb_terminal.duckdb`. The database is ignored by Git and is refreshed every 15 minutes while the application is running.
- Saved strategy definitions, backtest runs, and closed trades are also stored in that local DuckDB database.
- The data provider is isolated in `app/market_data.py` so a production provider can replace it later.
- Supported natural-language strategy format: `long when MA5 crosses above MA10 and exit when MA5 crosses below MA10`.
