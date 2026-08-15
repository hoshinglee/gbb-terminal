# Browser Interface

Primary sources: `app/web/src/`, `app/web/package.json`, and `app/web/vite.config.ts`

Fallback sources: `app/index.html`, `app/static/app.js`, `app/static/market-chart.js`, and `app/static/styles.css`

## Runtime Modes

GBB Terminal migrated one complete product slice at a time instead of rewriting every panel at once.

- A production Vite build under `app/static/react/` serves Strategy Lab, Option Lab, Stock Observatory, Market Pulse, and Company Intelligence.
- If that build is absent, FastAPI serves the vanilla application at `/`.
- `/` opens Strategy Lab; `/?lab=options`, `/?lab=stock`, `/?lab=market`, and `/?lab=intelligence` open the other canvases without a second frontend bundle or client router.
- Every laboratory is lazy-loaded as a separate release chunk so opening one canvas does not download every domain workspace.
- A validated `ticker` query parameter carries a symbol among Strategy Lab, Option Lab, Stock Observatory, and Company Intelligence without copying domain configuration.
- `/legacy` always serves the vanilla interface as an explicit migration fallback, but primary navigation no longer routes through it.
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

## React Stock Observatory

Release 0.6 turns the earlier quote panel into a stock research canvas:

1. Quote, day return, selected-window return, range, average volume, source status, observation time, `known_at`, retrieval time, and warnings remain visible.
2. The shared financial chart renders day/week/month/year candles, volume, RSI, MACD, and independent SMA, EMA, Bollinger, Darvas, and Fibonacci overlays.
3. Current option context exposes every Yahoo-reported expiry and all returned contracts with bid, ask, spread, volume, open interest, IV, and quote quality.
4. Direct actions open the same ticker in Strategy Lab or Option Lab.
5. A capped browser-local watchlist provides no-login symbol navigation. It is not represented as holdings or synced to a server.

Stock evidence remains useful when the option provider fails; chain errors do not erase available OHLCV. Changing the chart window does not silently change the selected current option expiry.

## React Market Pulse

Release 0.6 adds an evidence-first market canvas:

1. SPY, advancing/declining sector breadth, leaders/laggards, and the VIX proxy summarize current context without creating a market-timing verdict.
2. Sector cards and tables separate latest-day movement, trailing three-month return, and relative strength versus SPY.
3. S&P 500, VIX, dollar, gold, WTI, and 10-year-yield proxies display their own observation status and timing.
4. Provider readiness distinguishes a configured adapter from a successful upstream refresh.
5. Unavailable symbols remain visible as failed rows while successful cached or current rows continue rendering.

Sector links open Stock Observatory or Strategy Lab with the selected ETF ticker. Publication dates remain visible because cross-asset proxies do not share identical market hours.

## React Company Intelligence

Release 0.8 adds the company-business canvas at `/?lab=intelligence`; Release 0.9 extends it with source-backed business evidence:

1. Canonical legal name, CIK, current security, sector, and provenance keep business identity separate from ticker-market data.
2. Latest normalized TTM financial evidence and historical trailing valuation provide context before event analysis.
3. Earnings history shows reported revenue/EPS separately from calculated D0, D+5, D+20, benchmark-adjusted, and volume reactions.
4. Selecting a keyboard-focusable event keeps the company context in place while opening a detailed SEC evidence card and linked price/volume/reaction chart.
5. Aggregate move, direction frequency, drift, range, included sample size, and excluded sample count remain visible together.
6. Every event links to its SEC filing and exposes timing quality, accession, `known_at`, source facts, reaction-engine version, and caveats.
7. Network renders only persisted directional relationships, retains unresolved or unnamed counterparties, exposes evidence and history for every edge, and keeps the complete keyboard-accessible table available when the graph is capped.
8. Operations separates versioned segments, issuer-defined geography, and typed KPIs while preventing comparisons across incompatible definitions or reorganizations.
9. Guidance preserves original management wording, linked revisions, normalized ranges without invented precision, chronological source evidence, and explicitly labelled rule-based or manual outcomes.
10. Earnings, Financials, Valuation, Network, Operations, Guidance, and Sources load independently so an unavailable dataset does not erase the remaining company evidence.

The event chart supports pointer inspection and Left/Right/Home/End keyboard navigation. Network nodes support focused company navigation, unresolved-node inspection, direction/type/confidence filters, and internally scrollable narrow layouts without causing page-level overflow. Before-open and after-close alignment comes from the backend's trading-session model rather than browser date arithmetic. The canvas repeatedly states that historical reactions are descriptive and do not predict the next event.

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

Component tests cover mutually exclusive strategy selection, the stale-parameter regression, trailing-stop configuration, Darvas/Fibonacci overlays, option recipe replacement, lifecycle rediscovery, stock ticker handoff, local watchlists, sector breadth, Company Intelligence event selection, business-network navigation, unresolved counterparties, source dialogs, operating evidence, guidance history, and non-predictive language. Python browser-contract tests verify all five React canvases, evidence tabs, chart markers, lifecycle actions, V3 intelligence views, direct routes, return navigation, and fallback assets.

The shell includes skip navigation, labelled desktop/mobile navigation, explicit research-control labels, table captions, visible chart focus rings, and reduced-motion CSS. Smooth evidence scrolling becomes immediate when the operating system requests reduced motion.

The vanilla application remains a migration fallback until connected-browser parity, narrow-layout, and keyboard checks are signed off. All primary navigation now targets React, but the fallback is intentionally retained rather than deleted during the 0.6 implementation branch.

See [System Diagrams](system-diagrams.md) for the component-state and frontend-build diagrams.
