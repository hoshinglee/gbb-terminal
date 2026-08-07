# Market Replay

Sources: `src/gbb_terminal/market_data/charting.py`, `src/gbb_terminal/backtesting/engine.py`, `app/static/market-chart.js`, and `app/index.html`

## Business Definition

Market Replay places each strategy result back into its underlying price context. It helps a user inspect whether entries and exits occurred around trend changes, volatility expansion, unusual volume, or momentum extremes. It is evidence for understanding a historical run, not a live trading chart or investment recommendation.

The panel appears after the Trade Ledger so a user can move from accounting evidence to visual price evidence. Entry and exit markers use the same next-session fill dates and prices as the ledger.

## Interval Semantics

`build_market_chart(history)` returns four views over the exact research evaluation window:

| Control | Bar definition |
| --- | --- |
| Day | One actual US market session. |
| Week | Sessions grouped into a Friday-ending calendar week; the displayed range uses the first and last actual sessions. |
| Month | Sessions grouped by calendar month. |
| Year | Sessions grouped by calendar year. |

Aggregated bars use the first open, maximum high, minimum low, final close, and summed volume. Strategy position, signal position, and equity use the final observation in each aggregate bar.

Indicators are recalculated after aggregation. SMA 20 on the Week view therefore means twenty weekly bars, not a daily SMA sampled weekly. Earlier bars may be used for indicator warm-up but are not displayed outside the evaluation window. A line remains unavailable until its selected interval has enough history; the browser does not fill missing values.

## Indicators

The backend uses the approved `IndicatorRegistry` implementations:

- **SMA 20:** simple average of the last 20 closes.
- **EMA 20:** exponentially weighted average with a 20-bar span.
- **Bollinger 20/2σ:** SMA 20 plus and minus two population-standard-deviation bands.
- **Volume Average 20:** simple average of the last 20 bar volumes.
- **RSI 14:** Wilder-style smoothed relative strength index with 30 and 70 guide levels.
- **MACD 12/26/9:** fast EMA minus slow EMA, its 9-bar signal, and their histogram difference.

SMA, EMA, and Bollinger buttons independently switch price overlays without rerunning research. Volume and momentum panes remain visible because they provide distinct scale-aware context. RSI and MACD occupy separate vertical bands within the momentum canvas so their incompatible numeric scales are never overlaid.

## Function Definitions

- `build_market_chart(history)` validates the canonical OHLCV columns, creates each supported interval, calculates indicators, and serializes browser-safe values.
- `_aggregate_ohlcv(history, frequency)` preserves first/open, high/max, low/min, close/last, volume/sum, and final research state.
- `ResearchMarketChart.setData(payload, trades, symbol)` replaces the earlier run, resets the interval, maps trade events, and displays an explicit unavailable state for non-stock results.
- `ResearchMarketChart.render(highlightIndex)` redraws linked price, volume, and momentum canvases using one interval and crosshair index.

## Integrity And Limitations

- Indicator calculations use only current and earlier bars; appending future data cannot change an earlier daily point.
- Weekly, monthly, and yearly aggregation never invents non-trading sessions.
- Portfolio runs return `marketChart: null`; averaging different securities into a synthetic candle would not represent a tradable instrument.
- The current vanilla Canvas renderer intentionally avoids a runtime CDN dependency. A later React migration may replace its rendering layer while preserving the `marketChart` API contract.
