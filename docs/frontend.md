# Browser Interface

Sources: `app/static/index.html`, `app/static/app.js`, and `app/static/styles.css`

## Business definition

The browser interface gives a research user one workspace for translating ideas, comparing returns, inspecting trades, loading saved definitions, viewing options, and monitoring market context.

## Strategy Lab behavior

- `runBacktest` submits a new instruction or a loaded `strategy_id`.
- `drawChart` renders normalized strategy, buy-and-hold, and SPY equity.
- `renderTrades` presents all closed trades with absolute and percentage P&L.
- `renderCatalogue` builds the modal catalogue and YAML previews.
- `loadStrategyFromCatalogue` selects a persisted strategy without another LLM translation.
- `animateMonteCarlo` progressively renders percentile paths.

## UI state

`selectedStrategyId` is set when a catalogue item is loaded. Editing the instruction clears that ID, ensuring the next run translates and persists a new definition.
