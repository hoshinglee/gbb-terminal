# Browser Interface

Sources: `app/index.html`, `app/static/app.js`, `app/static/market-chart.js`, and `app/static/styles.css`

The vanilla browser application intentionally remains framework-free during the repository refactor. It provides four primary panels: Strategy Lab, Option Lab, Stock Observatory, and Market Pulse.

## Strategy workflow

1. **Define:** enter natural language, choose a validated template, or load a catalogue item.
2. **Configure:** edit typed values and choose fixed or guarded search modes.
3. **Test Design:** select a ticker or portfolio selection universe, market benchmark, timeframe, and costs. Relative-strength templates additionally choose the market benchmark, an automatically mapped Yahoo sector ETF, or an explicit custom symbol.
4. **Evidence:** inspect metrics, verdict, hoverable OHLCV/indicator equity chart, assumptions, benchmark risk table, validation evidence, parameter stability map, trade ledger, and linked market-replay panes.

The workflow header reflects actual progress: completed stages show a check, the current stage is highlighted, and selecting a stage scrolls to its section. Changing a strategy definition returns the workflow to Configure; changing research assumptions returns it to Test Design; a completed run activates Evidence.

Catalogue items are grouped by family and display parameter chips. Loading a catalogue item first clears the previous template selection and parameter controls, then renders only the selected strategy's editable configuration. Internal hashes are hidden. Canonical JSON or legacy YAML appears only under an Advanced export control. A loaded strategy uses its normalized description as grey placeholder text rather than replaying ambiguous original wording.

`drawChart` links date hover with line values and exact source observations. `renderCredibilityEvidence` explains evaluation boundaries, benchmark risk, Optuna/walk-forward selection, holdout evidence, Deflated Sharpe, stability, and performance decay. `renderTrades` shows closed and marked-open entries with absolute and percentage P&L. Stock Strategy Lab does not expose Monte Carlo until it models strategy-specific uncertainty; Option Lab retains its separate scenario-path simulation.

`ResearchMarketChart` receives the additive `marketChart` research payload after the trade ledger. Day, week, month, and year controls switch precomputed OHLCV intervals. SMA 20, EMA 20, and Bollinger 20/2σ buttons independently control price overlays. Linked crosshairs and hover details connect candles with volume, 20-bar average volume, RSI 14, MACD 12/26/9, strategy position, strategy equity, and trade markers. See [Market Replay](market-replay.md) for calculation semantics.

Option Lab builds core positions, loads current chain rows into leg inputs, displays payoff and Greeks, creates local paper positions, and appends lifecycle events without brokerage execution.

The proposed React/TypeScript interaction model and shadcn/ui component mapping are documented in [Strategy Lab UX Direction](strategy-lab-ux.md).
