# Browser Interface

Primary sources: `app/web/src/`, `app/web/package.json`, and `app/web/vite.config.ts`

Fallback sources: `app/index.html`, `app/static/app.js`, `app/static/market-chart.js`, and `app/static/styles.css`

## Runtime Modes

GBB Terminal migrated one complete product slice at a time instead of rewriting every panel at once.

- A production Vite build under `app/static/react/` serves Strategy Lab, Option Lab, Market Pulse, and Company Intelligence.
- If that build is absent, FastAPI serves the vanilla application at `/`.
- `/` opens Strategy Lab; `/?lab=options`, `/?lab=market`, and `/?lab=intelligence` open the other canvases without a second frontend bundle or client router.
- Every laboratory is lazy-loaded as a separate release chunk so opening one canvas does not download every domain workspace.
- A validated `ticker` query parameter carries a symbol among Strategy Lab, Option Lab, and Company Intelligence without copying domain configuration. Legacy `lab=stock` URLs canonicalize to Company Intelligence with the ticker intact.
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

Release 0.4.3 replaces the form-led Strategy Lab with a research canvas; Release 0.10 simplifies its common path to Idea → Backtest → Current Signal:

1. Use the natural-language composer, a quick-start card, or `Cmd/Ctrl+K` command search.
2. Edit validated rule values directly inside a compact readable rule sentence and optionally add a trailing-stop chip.
3. Keep ticker, timeframe, and Run Research in the compact context bar.
4. Open benchmark, costs, relative-strength reference, portfolio universe, and validation settings only through the assumptions side sheet.
5. Choose among six plain-language starter theses without configuring engine internals, or retain natural-language and saved-strategy paths.
6. Inspect the market preview while defining the idea, then review Evidence & Signal, Equity & Drawdown, and the Full Trade Ledger. Robustness and assumptions remain under Advanced Validation.
7. Read current target state, observation date, next-open meaning, causal rule values, latest transition, and latest trade directly from the backend result.

On wide screens, the composer and financial chart default to a resizable side-by-side layout. Panel constraints use explicit percentages: the composer can occupy 24–68% and the chart retains at least 32%. A canvas toolbar switches to a vertically stacked layout when the user wants full-width rule editing and full-width chart inspection. The choice is stored locally in the browser; narrow screens always stack automatically.

Desktop and mobile shells expose the same laboratory navigation. The compact control bar wraps into full-width strategy and run rows on narrow screens, long evidence tables scroll horizontally, and chart detail bars remain in document flow instead of covering candles when controls wrap.

`ResearchWorkspaceProvider` owns one discriminated selection state. Choosing natural language, a template, or a catalogue item clears the other modes, their parameter ranges, and stale evidence. V2 catalogue items restore editable typed parameters; legacy catalogue entries remain runnable but clearly read-only.

Natural-language instructions first call the proposal endpoint. A confirmation dialog displays the normalized description, risk controls, clarification assumptions, provider, and any existing catalogue match. Provider output is constrained JSON; server-generated compatibility YAML remains hidden from ordinary users, and translated input never becomes executable Python.

`CurrentSignalPanel` never recomputes a strategy in the browser. It renders `currentSignal` from the same deterministic Python signal/execution frame as the backtest. Pre-0.10 persisted results remain readable and display a rerun prompt when that field is absent.

The initial single-stock symbol is NVDA. The chart badge shows that symbol rather than repeating provider/delay metadata; source, delay/staleness, observation date, and quality warnings remain visible in the provenance line above the canvas.

## React Option Lab

Release 0.10 places an approachable **Plan → Compare → Scenario** path in front of the complete Release 0.5 engine:

1. Plan from the persistent ticker plus outlook, horizon, optional price/range, share ownership/acquisition preference, acceptable loss, and capital budget.
2. Compare up to three validated structures side by side. Debit/credit, capital, gross collateral, loss/gain shape, break-even, strikes, expiry, aggregate Greeks, bid/ask quality, and trade-offs remain visible; no candidate is called optimal.
3. Ask the primary “What if TICKER is $X on DATE?” question. React sends the selected position to the server and only renders the returned modeled value, P&L, remaining time, break-even relation, Greeks, assumptions, provenance, and warnings.
4. Selecting a candidate opens the existing detailed leg builder while preserving the comparison. Full simulation and the paper journal are optional progressive-disclosure sections.
5. Historical earnings-event movement and selected-expiry ATM straddle context preserve source/as-of labels and explicitly avoid a mispricing conclusion.

The normal planner excludes uncovered short calls. Covered calls require owned shares; cash-secured puts require explicit willingness to acquire shares. A neutral request without either condition receives an explicit warning that the supported defined-risk verticals remain directional.

The underlying Release 0.5 workflow remains available:

1. Position-recipe cards replace the long position-type form while editable leg cards keep every contract assumption visible.
2. A current-chain side sheet follows Target Leg → Expiry → Contract, fills only the selected leg, and displays all Yahoo-reported expiries and every returned strike with executable-side quote context.
3. Model assumptions remain in a side sheet; ticker, spot, chain loading, and simulation stay in the compact context bar.
4. Evidence tabs show expiry payoff, price/time slices, animated underlying and position-P&L paths, and scaled Greeks.
5. Immutable run and paper-position sheets restore earlier work; the lifecycle card journals validated hold observations, closes, rolls, share trades, added option legs, exercise, expiry, and assignment transitions.

The progress rail advances only after successful planner and scenario responses. Changing the ticker or outlook clears stale comparison/scenario state. Editing a detailed economic input still invalidates full-simulation evidence, while changing only a paper-position name does not mutate the immutable run.

Scenario SVGs support pointer inspection and Left/Right/Home/End keyboard navigation. Animation honors the operating system reduced-motion preference.

## React Market Pulse

Release 0.6 adds an evidence-first market canvas; Release 0.10 adds current-constituent research:

1. SPY, advancing/declining sector breadth, leaders/laggards, and the VIX proxy summarize current context without creating a market-timing verdict.
2. Sector cards and tables separate latest-day movement, trailing three-month return, and relative strength versus SPY.
3. S&P 500, VIX, dollar, gold, WTI, and 10-year-yield proxies display their own observation status and timing.
4. Provider readiness distinguishes a configured adapter from a successful upstream refresh.
5. Unavailable symbols remain visible as failed rows while successful cached or current rows continue rendering.
6. A Download/Refresh S&P 500 control starts a persisted background job, shows progress, supports cancellation, and resumes by skipping fresh complete records.
7. Sector cards are selection controls rather than ETF-to-company links. The selected sector expands in Market Pulse with all current-snapshot constituents.
8. The constituent treemap sizes known companies by calculated point-in-time market capitalization, isolates missing values in a dashed equal-area region, and colors only observed daily movement.
9. Top-20 daily gainers and losers remain descriptive rankings; a complete expandable table is the keyboard and narrow-layout alternative.

Constituent links open Company Intelligence with only a validated ticker. Sector ETF strategy links remain separate. Publication dates remain visible because cross-asset proxies do not share identical market hours, and current public membership is never represented as historical index evidence.

## React Company Intelligence

Release 0.8 adds the company-business canvas at `/?lab=intelligence`; Release 0.9 extends it with source-backed business evidence; Release 0.10 makes it the canonical individual-stock experience:

1. Canonical legal name, CIK, current security, sector, and provenance keep business identity separate from ticker-market data.
2. Overview retains only useful security context from Stock Observatory: current price, daily movement, browser-local watchlist navigation, and market-data freshness. Technical-analysis and option-chain work remain in Strategy Lab and Option Lab.
3. Financials loads all available annual, quarterly, and TTM normalized history together. Its history is independent of valuation and market-chart windows.
4. Valuation owns a local 1/3/5/10-year or maximum window, fixed historical statistics, a keyboard-inspectable history chart, and text-labelled Below History, Typical Range, Above History, Extreme vs History, NM, unavailable, and low-sample regimes.
5. Earnings owns its benchmark and 3/5-year market window. Selecting a keyboard-focusable event marks and centers that event on a daily candlestick/volume chart inside Event Evidence.
6. Reported revenue/EPS remain neutral. Observed price reactions and comparable financial changes use semantic positive/negative treatment paired with arrows or text; valuation color never implies buy/sell advice.
7. Aggregate move, direction frequency, drift, range, included sample size, and excluded sample count remain visible together.
8. Every event links to its SEC filing and exposes timing quality, accession, `known_at`, source facts, reaction-engine version, and caveats.
9. Sources exposes module health, SEC refresh, persisted progress, cooperative cancellation, and explicit provider/parser/extraction/no-disclosure states.
10. Network renders only persisted directional relationships, retains unresolved or unnamed counterparties, exposes evidence and history for every edge, and keeps the complete keyboard-accessible table available when the graph is capped.
11. Operations separates versioned segments, issuer-defined geography, and typed KPIs while preventing comparisons across incompatible definitions or reorganizations.
12. Guidance preserves original management wording, linked revisions, normalized ranges without invented precision, chronological source evidence, and explicitly labelled rule-based or manual outcomes.
13. Overview, Financials, Valuation, Earnings, Network, Operations, Guidance, and Sources retain independent failure states so one unavailable provider does not erase the remaining company evidence.

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

Component tests cover mutually exclusive strategy selection, the stale-parameter regression, trailing-stop configuration, Darvas/Fibonacci overlays, option recipe replacement, lifecycle rediscovery, local watchlists, sector breadth, Company Intelligence period independence, event selection, business-network navigation, unresolved counterparties, source dialogs, operating evidence, guidance history, and non-predictive language. Python browser-contract tests verify all four React canvases, legacy-stock canonicalization, evidence tabs, chart markers, lifecycle actions, V3 intelligence views, direct routes, return navigation, and fallback assets.

The shell includes skip navigation, labelled desktop/mobile navigation, explicit research-control labels, table captions, visible chart focus rings, and reduced-motion CSS. Smooth evidence scrolling becomes immediate when the operating system requests reduced motion.

The vanilla application remains a migration fallback until connected-browser parity, narrow-layout, and keyboard checks are signed off. All primary navigation now targets React, but the fallback is intentionally retained rather than deleted during the 0.6 implementation branch.

See [System Diagrams](system-diagrams.md) for the component-state and frontend-build diagrams.
