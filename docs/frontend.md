# Browser Interface

Primary sources: `app/web/src/`, `app/web/package.json`, and `app/web/vite.config.ts`

Fallback sources: `app/index.html`, `app/static/app.js`, `app/static/market-chart.js`, and `app/static/styles.css`

## Runtime Modes

GBB Terminal migrates one complete product slice at a time instead of rewriting every panel at once.

- A production Vite build under `app/static/react/` serves the React Strategy Lab and Option Lab.
- If that build is absent, FastAPI serves the vanilla application at `/`.
- `/` opens Strategy Lab and `/?lab=options` opens Option Lab without requiring a second frontend bundle or client router.
- Strategy Lab and Option Lab are lazy-loaded as separate release chunks so opening one laboratory does not download the other laboratory's workspace code.
- `/legacy` always serves the vanilla interface. React navigation sends Stock Observatory and Market Pulse there with a `panel` query parameter.
- The legacy sidebar includes **Return To Research Canvas**, so users never need to edit the browser URL manually.
- Both interfaces call the same FastAPI endpoints and use the same DuckDB database.

Generated React assets are ignored by Git. Build them locally or in deployment automation:

```bash
cd app/web
npm install
npm run build
```

For live frontend development, keep FastAPI on port 8000 and run `npm run dev`. Vite serves port 5173 and proxies `/api` to FastAPI.

## React Strategy Lab

Release 0.4.3 replaces the form-led Strategy Lab with a research canvas:

1. Use the natural-language composer, a quick-start card, or `Cmd/Ctrl+K` command search.
2. Edit validated rule values directly inside a compact readable rule sentence and optionally add a trailing-stop chip.
3. Keep ticker, timeframe, and Run Research in the compact context bar.
4. Open benchmark, costs, relative-strength reference, portfolio universe, and validation settings only through the assumptions side sheet.
5. Inspect the market preview while defining the idea, then review results in Overview, Equity & Drawdown, Trades, Robustness, and Assumptions tabs.

On wide screens, the composer and financial chart default to a resizable side-by-side layout. Panel constraints use explicit percentages: the composer can occupy 24–68% and the chart retains at least 32%. A canvas toolbar switches to a vertically stacked layout when the user wants full-width rule editing and full-width chart inspection. The choice is stored locally in the browser; narrow screens always stack automatically.

Desktop and mobile shells expose the same laboratory navigation. The compact control bar wraps into full-width strategy and run rows on narrow screens, long evidence tables scroll horizontally, and chart detail bars remain in document flow instead of covering candles when controls wrap.

`ResearchWorkspaceProvider` owns one discriminated selection state. Choosing natural language, a template, or a catalogue item clears the other modes, their parameter ranges, and stale evidence. V2 catalogue items restore editable typed parameters; legacy catalogue entries remain runnable but clearly read-only.

Natural-language instructions first call the proposal endpoint. A confirmation dialog displays the normalized description, risk controls, clarification assumptions, provider, and any existing catalogue match. Provider output is constrained JSON; server-generated compatibility YAML remains hidden from ordinary users, and translated input never becomes executable Python.

The initial single-stock symbol is NVDA. The chart badge shows that symbol rather than repeating provider/delay metadata; source, delay/staleness, observation date, and quality warnings remain visible in the provenance line above the canvas.

## React Option Lab

Release 0.5 ports the complete core option workflow to the React canvas:

1. Position-recipe cards replace the long position-type form while editable leg cards keep every contract assumption visible.
2. A current-chain side sheet follows Target Leg → Expiry → Contract, fills only the selected leg, and displays all Yahoo-reported expiries and every returned strike with executable-side quote context.
3. Model assumptions remain in a side sheet; ticker, spot, chain loading, and simulation stay in the compact context bar.
4. Evidence tabs show expiry payoff, price/time slices, animated underlying and position-P&L paths, and scaled Greeks.
5. Immutable run and paper-position sheets restore earlier work; the lifecycle card journals validated hold observations, closes, rolls, share trades, added option legs, exercise, expiry, and assignment transitions.

The progress rail advances from Build to Explore only after a simulation response and to Journal only after a persisted paper position. Changing an economic input invalidates stale scenario evidence. Changing only the paper-position name does not invalidate the simulation.

Scenario SVGs support pointer inspection and Left/Right/Home/End keyboard navigation. Animation honors the operating system reduced-motion preference.

## Financial Charts

TradingView Lightweight Charts renders:

- Daily, weekly, monthly, and yearly candlesticks from research results.
- Strategy-aware overlays plus independent SMA, EMA, Bollinger, Darvas, and Fibonacci toggles. Darvas templates use their selected box/confirmation values; Fibonacci templates use their selected rolling window/ratio.
- Volume and 20-bar average volume.
- RSI and MACD panes.
- Entry and exit markers mapped to the selected interval.
- Crosshair details for date range, OHLCV, RSI, position, and active overlays.
- Keyboard inspection with Left/Right Arrow and Home/End, with the selected OHLCV or equity values announced through an accessible live summary.
- Strategy, buy-and-hold, SPY, and strategy drawdown evidence.

The pre-run preview loads raw OHLCV from `/api/v2/chart-data`; browser-side indicators exist only for immediate visualization. Research evidence and fills always come from backend calculations.

## Evidence Design

- Overview keeps the plain-language verdict subordinate to return, drawdown, exposure, trade count, and benchmark risk.
- Equity & Drawdown identifies strategy, buy-and-hold, and SPY and exposes exact values on hover.
- Trades lists closed and marked-open positions with entry, exit/as-of date, absolute P&L, percentage P&L, holding period, and execution cost.
- Robustness shows all parameter-search attempts, the stability region, untouched final test, Deflated Sharpe evidence, performance decay, and regime slices.
- Assumptions records the execution model, capital, costs, evaluation dates, sessions, and benchmarks.

## Validation

Run the frontend checks from `app/web`:

```bash
npm run typecheck
npm run test:run
npm run build
```

Component tests cover mutually exclusive strategy selection, the stale-parameter regression, trailing-stop configuration, Darvas/Fibonacci overlays, option recipe replacement, covered-call share cover, and current-contract mapping. Python browser-contract tests verify that both React labs, evidence tabs, chart markers, lifecycle actions, return navigation, and legacy assets remain present.

The shell includes skip navigation, labelled desktop/mobile navigation, explicit research-control labels, table captions, visible chart focus rings, and reduced-motion CSS. Smooth evidence scrolling becomes immediate when the operating system requests reduced motion.

The vanilla Strategy Lab remains a migration fallback. Its workflow header, parameter forms, research evidence, trade ledger, and canvas-based market replay stay unchanged until all primary panels reach React parity.

See [System Diagrams](system-diagrams.md) for the component-state and frontend-build diagrams.
