# Browser Interface

Sources: `app/index.html`, `app/static/app.js`, and `app/static/styles.css`

The vanilla browser application intentionally remains framework-free during the repository refactor. It provides four primary panels: Strategy Lab, Option Lab, Stock Observatory, and Market Pulse.

## Strategy workflow

1. **Define:** enter natural language, choose a validated template, or load a catalogue item.
2. **Configure:** edit typed values and choose fixed or guarded search modes.
3. **Test Design:** select ticker/universe, benchmark, timeframe, commission, and slippage.
4. **Evidence:** inspect metrics, verdict, hoverable OHLCV/indicator equity chart, assumptions, and trade ledger.

Catalogue items are grouped by family and display parameter chips. Internal hashes are hidden. Canonical JSON or legacy YAML appears only under an Advanced export control. A loaded strategy uses its normalized description as grey placeholder text rather than replaying ambiguous original wording.

`drawChart` links date hover with line values and exact source observations. `animateMonteCarlo` reveals percentile paths progressively. `renderTrades` shows closed and marked-open entries with absolute and percentage P&L.

Option Lab builds core positions, loads current chain rows into leg inputs, displays payoff and Greeks, creates local paper positions, and appends lifecycle events without brokerage execution.
