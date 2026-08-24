# Product Backlog

This backlog turns observed hobbyist-investor workflows into research capabilities. It is not a catalogue of recommended trades. Every item must preserve visible assumptions, public-data limitations, assignment mechanics, financing costs, and the possibility of loss.

## Release 0.5 — Option Lab Completion

Implementation status: P0.1–P0.5 are implemented on the release 0.5 branch. Connected-browser review and the broader multi-leg golden-fixture matrix remain release gates in `release-checklist.md`.

### P0.1 — Expiry-Aware Current Chain

**Problem:** The current picker silently loads the provider's nearest expiry and truncates the visible contracts. Users cannot tell how to inspect another date or whether the requested strike exists elsewhere.

**Experience:**

1. Select one target leg.
2. Select an expiry from every date currently reported by Yahoo.
3. Inspect every call or put returned for that expiry.
4. Load one contract into only the target leg.

**Acceptance criteria:**

- `GET /api/v2/options/chains/{ticker}?expiration=YYYY-MM-DD` validates the requested date and returns `expiration`, all `expirations`, and every contract for the selected date.
- DuckDB caches each requested ticker/expiry snapshot independently without allowing a later expiry to replace the default nearest-expiry cache.
- The picker shows calendar date, days to expiry, bid, ask, last, spread, volume, open interest, IV, and the price used for the selected long or short leg.
- Long legs default to the ask and short legs default to the bid. Last or midpoint is used only as a labelled fallback.
- The UI explicitly presents **Target Leg → Expiry → Contract** and never describes a nearest-expiry snapshot as the complete option market.
- Manual assumptions remain available when Yahoo is unavailable.

### P0.2 — Position Recipe V2

**Problem:** A flat row of position names does not explain economic obligations, required collateral, leg relationships, or why dates and strikes must match.

**Acceptance criteria:**

- Recipes are grouped as Directional, Income, Defined Risk, and Financing/Parity.
- Each recipe declares leg roles, share requirements, expiry policy, strike policy, capital profile, maximum-risk shape, and a plain-language purpose.
- Multi-leg recipes visibly identify which legs must share an expiry and which strike ordering is required.
- Selecting another recipe replaces incompatible legs and assumptions while retaining only ticker and model-level context.
- The initial catalogue includes the existing core positions plus **Conversion**: long 100 shares, long put, and short call with matching strike, expiry, and quantity.
- Invalid recipe structures are rejected by Pydantic before pricing or persistence.

### P0.3 — Persisted Simulation Runs

**Problem:** A chart result is transient. Users need to compare different strategies and assumptions without treating every simulation as a brokerage position.

**Acceptance criteria:**

- Every simulation creates an immutable local research-run record containing the request, result, creation time, model version, and data provenance.
- Recent runs can be listed and loaded back into Option Lab.
- A paper position references the exact simulation run from which it was created.
- Editing a draft invalidates the displayed result but never mutates an earlier run or paper ledger.
- Multiple runs for the same ticker and recipe remain distinct and reproducible through fixed seeds and explicit model assumptions.

### P0.4 — Conversion Financing Scenario

**Source workflow:** Buy 100 shares, buy one put, and sell one call at the same strike and expiry. The user wants to understand whether the premium difference creates a “risk-free” return.

**Acceptance criteria:**

- The simulation shows initial share outlay, long-option debit, short-option credit, net capital committed, locked terminal proceeds, nominal return, holding days, and annualized return.
- The result compares annualized return with the configured cash/financing rate and labels the difference.
- A flat terminal payoff is described as a locked idealized payoff, never an unconditional risk-free profit.
- Warnings cover executable bid/ask prices, dividends, early assignment, reinvestment timing, taxes, fees, and corporate actions.
- The lifecycle playbook explains that early assignment delivers the covered shares while the long put remains an asset.

### P0.5 — LEAP Call Management Playbook

**Source workflow:** A user sells a long-dated call and wants to explore a future stock rally, buying shares to become covered, adding a higher-strike call to cap loss, rolling, or adding a cash-secured put.

**Acceptance criteria:**

- A naked short call is always labelled **uncapped risk**; premium income is never presented without the upside-loss path.
- The scenario workspace provides explicit branches rather than one “optimal” recommendation:
  - Continue the current exposure.
  - Buy shares and transform the short call into a covered call.
  - Add a higher-strike long call and transform it into a defined-risk call spread.
  - Roll strike or expiry.
  - Add a separately collateralized short put and show the additional assignment obligation.
- Branches display trigger assumptions, required cash/collateral, resulting shares and legs, changed break-even, and remaining risks.
- Paper lifecycle events support buying/selling shares and adding a validated option leg, preserving complete before/after state.
- “Buy shares at the strike” and similar paths must use the user's actual assumed purchase price; the UI must not imply that later execution is guaranteed.

## Release 0.6 — Complete React Migration

Implementation status: P0.6 and P0.7 are implemented on the release 0.6 branch. P0.8 remains open until connected-browser, narrow-layout, and keyboard parity checks are completed.

### P0.6 — Stock Observatory Revamp

- Port quote, OHLCV, volume, current-chain context, technical overlays, provenance, and cached-data warnings from the vanilla panel.
- Add watchlist-oriented navigation without introducing authentication or brokerage execution.
- Link a selected stock directly into Strategy Lab and Option Lab without copying form values manually.

### P0.7 — Market Pulse Revamp

- Port sector performance, relative strength, macro proxies, and provider status into a React market canvas.
- Make observation date, `known_at`, source, staleness, and publication frequency visible.
- Link a sector or market symbol into stock and strategy research.

### P0.8 — Legacy Retirement Gate

- Keep `/legacy` until Strategy Lab, Option Lab, Stock Observatory, and Market Pulse have API, interaction, accessibility, and narrow-layout parity.
- Remove legacy navigation labels only after browser-contract and connected-browser acceptance tests pass.

## Release 0.7 — Company Intelligence Foundation

Implementation status: INT-01 through INT-04 are implemented on the Release 0.7 branch. The backend foundation exit criteria are complete; a Company Intelligence browser canvas remains a later product milestone.

### INT-01 — Canonical Company Identity

- Persist stable company identity by `company_id` and normalized CIK.
- Resolve active or historical ticker mappings to the same company.
- Preserve ticker changes, alternate share classes, and delistings as dated security mappings.
- Ingest the official SEC ticker/CIK/exchange directory with explicit source limitations and retrieval context.

### INT-04 — V3 Company Intelligence APIs

- Resolve ticker paths through canonical company identity rather than storing business data under ticker keys.
- Expose company overview, point-in-time source facts, and normalized annual/quarterly/TTM metrics.
- Keep provenance, as-of context, schema versions, warnings, and source lineage visible.
- Preserve every V2 Stock Observatory, Strategy Lab, and Option Lab contract.

## Release 0.8 — Valuation And Earnings Intelligence

Implementation status: INT-05 through INT-08 are implemented on the Release 0.8 branch. Company Intelligence now has an end-user React canvas in addition to its strict V3 domain contracts.

### INT-05 — Historical Point-In-Time Valuation

- Align adjusted security closes with only normalized SEC facts known by each New York market close.
- Persist versioned daily/weekly P/E, P/S, P/B, EV/Revenue, EV/EBITDA, P/FCF, earnings-yield, and FCF-yield observations.
- Return explicit `nm`/unavailable states, own-history percentiles, medians, ranges, z-scores, and lineage.

### INT-06 — Earnings Events And Reactions

- Persist stable, source-backed fiscal events using exact or date-only SEC filing evidence.
- Align before-open, after-close, intraday, weekend/holiday, and unknown-time events to observed trading sessions.
- Calculate D0 through D+60, benchmark-adjusted reaction, opening gap, abnormal volume, path evidence, and sample-aware aggregates.

### INT-07 — Earnings Reaction Explorer

- Add Company Intelligence as a fifth lazy-loaded React canvas with direct ticker navigation.
- Keep reported facts separate from calculated reactions while preserving event source links and caveats.
- Add selectable event history, accessible price/volume/reaction chart, normalized financial progression, and valuation context.

### INT-08 — Analyst Estimates Boundary

- Define strict provider-neutral revenue/EPS expectation models with observation and `known_at` timestamps.
- Support revision history, exact fiscal mapping, empty coverage, and a Git-ignored manual fixture adapter.
- Do not scrape or select a commercial estimates vendor and do not turn expectations into reported facts.

## Release 0.9 — Evidence And Business Network

Implementation status: INT-09 through INT-13 storage, domain, strict APIs, evidence-first React views, automated contracts, and the connected-browser acceptance sweep are implemented on the Release 0.9 branch. Permitted public-document collectors remain open; no graph edge or extracted claim may precede inspectable evidence.

### INT-09 — Evidence Documents And Source-Backed Spans

- Version permitted public documents by stable company/source/external identity and SHA-256 content fingerprint.
- Preserve publication, `known_at`, retrieval, source URL, parse state, and quality context.
- Persist independently retrievable exact-text spans with source location and extraction metadata.
- Link one or multiple support, context, or contradiction spans to typed structured claims.
- Reject unsupported spans after parsing failure and keep empty public-disclosure coverage explicit.

### INT-10 — Customer And Supplier Relationships

- Persist directional supplier, customer, manufacturer, distributor, partner, and explicitly disclosed competitor relationships.
- Distinguish resolved companies from raw or unnamed counterparties and retain economic exposure when disclosed.
- Require evidence for sourced/disclosed edges, accumulate duplicate evidence without duplicate economic edges, and preserve historical changes.

### INT-11 — Interactive Relationship Graph

- Render only persisted relationships with visible direction, type, confidence, date context, and evidence access.
- Support focused expansion and company navigation without implying that the public network is exhaustive.
- Keep graph exploration separate from unsupported network-derived trading signals.

### INT-12 — Segment, Geography, And KPI Intelligence

- Version issuer-reported segment definitions and preserve reorganizations rather than silently combining incompatible history.
- Retain fiscal period, units, `known_at`, and evidence for segment, geographic, and company-specific KPI observations.
- Start with trustworthy depth for curated US companies instead of claiming universal standardized coverage.

### INT-13 — Guidance And Management Commitments

- Preserve immutable source-backed guidance, revisions, ranges, qualitative commitments, and applicable periods.
- Reconcile objective outcomes through deterministic rules and label manual or interpretive assessments explicitly.
- Keep original wording and evidence available; LLM summaries never replace source statements.

## Release 0.10 — Personal Research Completion

Implementation status: INT-18 public-document collection, INT-14/INT-16/INT-17 Company Intelligence consolidation, INT-15 universe caching, MKT-01 sector constituent drill-down, STR-01 Strategy Lab simplification, and OPT-01 Options Planner are implemented on the Release 0.10 branch. The integrated automated and connected-browser acceptance sweep is complete; public-launch environment stabilization remains intentionally deferred to the release-readiness checklist.

### INT-14 — Canonical Company Research

- Retire Stock Observatory from primary React navigation and canonicalize legacy stock URLs without losing ticker context.
- Retain current price, daily move, browser-local watchlist navigation, market-data provenance, and reusable V2 OHLCV contracts inside Company Intelligence.
- Keep technical-strategy and option-chain work in their purpose-built laboratories rather than duplicating them on the company overview.

### INT-16 — Independent Time Controls And Event Evidence

- Load every available normalized annual, quarterly, and TTM period independently from price and valuation windows.
- Give valuation its own historical window and fixed point-in-time history/statistics.
- Keep every supported earnings event and place a marked, focused daily candlestick/volume chart in Event Evidence with a three-year default and five-year maximum.

### INT-17 — Financial Visual Semantics

- Keep absolute financial values neutral and add positive/negative treatment only to comparable changes and observed market reactions.
- Label valuation as Below History, Typical Range, Above History, Extreme vs History, NM, unavailable, or low sample without implying cheap/expensive recommendations.
- Pair every semantic color with text or an icon and keep provider/stale/missing states distinct from deterioration.

### INT-18 — Public Document Collection

- Discover, cache, version, parse, and extract supported SEC filings and relevant exhibits through a resilient local refresh job.
- Require inspectable evidence spans for persisted relationships, operating observations, and guidance statements.
- Expose source health, diagnostics, progress, cancellation, CLI parity, and explicit failure/no-disclosure states.

### INT-15 — S&P 500 Local Research Universe

- Persist provider-neutral, versioned current-composition snapshots without representing them as licensed historical membership.
- Prepare approximately three years of market, SEC financial, valuation, and earnings context through bounded resumable jobs.
- Preserve per-company completion, partial, failed, skipped, and cancelled states with retry diagnostics and stale-cache reuse.
- Expose matching FastAPI, CLI, and Market Pulse download/refresh controls without hard-coding membership in React.

### MKT-01 — Sector Constituent Drill-Down

- Keep sector selection inside Market Pulse and rank the top 20 daily gainers and losers.
- Size treemap rectangles by calculated point-in-time market capitalization and color them by daily movement.
- Isolate missing-cap constituents in an explicitly labelled equal-area fallback instead of inventing capitalization.
- Preserve direct Company Intelligence navigation plus an accessible, narrow-layout table alternative.

### STR-01 — Idea → Backtest → Current Signal

- Offer six understandable starter theses while preserving natural-language, saved-strategy, and editable declarative-rule paths.
- Keep the ordinary path to ticker, strategy, timeframe, and Run; move research-engine controls under Advanced Validation.
- Return target and executed state, observation date, next-open timing, causal rule values, and latest transition from the backtest engine itself.
- Put honest benchmark evidence, current signal, and latest trade first while retaining equity, market replay, full ledger, parameter search, and robustness evidence.

### OPT-01 — Plan → Compare → Scenario

- Start from outlook, horizon, optional target/range, owned shares, willingness to acquire, acceptable loss, and capital budget rather than requiring chain fluency.
- Build only existing validated long-option, covered/cash-secured, and defined-risk vertical structures; never surface an uncovered short call in the normal planner.
- Compare executable-side quote inputs, entry debit/credit, capital and gross collateral, terminal risk/reward shape, break-even, expiry/strikes, and aggregate Greeks without claiming an optimum.
- Price future price/date scenarios only in Python and preserve explicit model, IV, rate, dividend, quote-quality, and beyond-expiry warnings.
- Keep the detailed builder, immutable simulations, and paper lifecycle backward compatible and optional after planning.
- Show source-backed historical earnings movement and separately labelled selected-expiry ATM straddle context without treating the difference as mispricing.

## Release 0.11 — Decision Risk Context

### DRC-01 — Personal Risk Policy And Portfolio Context

Implementation status: local capital, liquid cash, manual holdings, canonical company resolution, immutable risk-policy versions, policy snapshots, V2 APIs, compact global editing, and storage/API/domain tests are implemented. Attaching snapshots to specific research and option decisions remains a later Decision Center integration.

- Keep portfolio sizing context separate from strategy logic, ticker selection, and instrument construction.
- Persist manual holdings even when public quote providers are unavailable; retain unresolved normalized tickers until canonical identity is available.
- Require explicit limits for normal target size, single-name exposure, assignment exposure, short-option collateral, unencumbered cash, and portfolio stress loss.
- Append a new immutable policy version on every save and allow stable snapshots for future decision records.
- Keep all existing labs useful when portfolio context is absent and never treat these user-defined limits as recommendations.

### DRC-02 — Company Thesis Card

Implementation status: company-scoped thesis versions, user-owned statuses, evidence/moat/risk/catalyst/invalidation fields, validated source-span references, exact-text/interpretation separation, and stable snapshots are implemented.

### DRC-03 — Position Sizer And Instrument Fit

Implementation status: target/maximum exposure before instrument choice, current holding context, shares and validated options fit, assignment/collateral/cash/concentration/stress policy gates, explicit arithmetic, and incomplete-context handling are implemented.

### DRC-04 — Position Expression Comparator

Implementation status: ownership, lower accumulation, income, and defined-risk objectives compare eligible direct shares and current Option Lab structures without optimality claims; provider failure retains direct-share planning and deep links.

### DRC-05 — Entry Planner And Stress Gates

Implementation status: versioned staged tranches, three execution modes, three escape choices, preferred/maximum prices, opportunity reserve, -20/-40/-60 stock scenarios, IV/time assumptions, server-side option pricing, portfolio impact, and policy gates are implemented.

### DRC-06 — Decision Journal And Process Review

Implementation status: all planned lifecycle states, frozen thesis/policy/intent/expression/entry snapshots, append-only revisions, company/state/type/date/review filters, reopening, separate process/outcome review, and optional Option Lab paper-position references are implemented.

## Cross-Release Usefulness Enhancements

1. Compare saved stock and option research runs in one project workspace.
2. Build prospective historical option-chain datasets from scheduled local snapshots.
3. Add watchlists, paper alerts, assignment calendars, and expiry reminders.
4. Add cost, dividend, rate, IV, and early-assignment sensitivity matrices.
5. Add importable community recipes with schema compatibility checks.
6. Add optional local user profiles before considering hosted authentication.
7. Add portfolio-level capital, collateral, concentration, and correlated-loss views.

## Research Safety Definition Of Done

- No generated Python, JavaScript expressions, or YAML are executed.
- No result is labelled risk-free unless every required cash flow is guaranteed by an identified instrument and the display still states execution, funding, tax, and operational limitations.
- Bid/ask direction, multiplier, quantity, expiry, strike, dividend, rate, and data timestamp are inspectable.
- Unlimited or uncapped loss is never hidden behind premium income or probability estimates.
- Every paper transformation reconciles cash, shares, open contracts, collateral, realized P&L, and the immutable event history.
