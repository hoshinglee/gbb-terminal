# Browser Interface

Sources: `app/static/index.html`, `app/static/app.js`, and `app/static/styles.css`

## Business definition

The browser interface gives a research user one workspace for translating ideas, comparing returns, inspecting trades, loading saved definitions, viewing options, and monitoring market context.

## Strategy Lab behavior

- `runBacktest` submits a loaded `strategy_id` directly or requests an assisted proposal for a new instruction.
- `showProposal` opens a confirmation dialog with normalized logic, ambiguities, duplicate status, semantic key, and YAML.
- `confirmProposal` submits the confirmed YAML for persistence and backtesting.
- `drawChart` renders normalized strategy, buy-and-hold, and SPY equity.
- `renderTrades` presents closed and currently open trades with dates, prices, absolute P&L, and percentage P&L. It also opens the ledger after a successful run.
- `renderCatalogue` builds the modal catalogue and YAML previews.
- `loadStrategyFromCatalogue` selects a persisted strategy without another LLM translation.
- `animateMonteCarlo` progressively renders percentile paths.

## UI state

`selectedStrategyId` is set when a catalogue item is loaded. The text area is cleared and the strategy's normalized description appears as grey placeholder text, so transformed LLM output is not presented as the user's original wording. Editing the field clears the selected ID and starts a new assisted proposal flow.

`pendingProposal` exists only in browser memory between proposal and confirmation. Cancelling the dialog makes no database change.
