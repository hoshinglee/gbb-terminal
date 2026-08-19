# Release Readiness

This checklist separates research correctness from launch-environment stabilization. Release 0.4 may continue without prematurely treating local-machine launch checks as complete.

## Release 0.4 — Research Credibility

- [x] Canonical Strategy Model V2 rejects unknown fields and stale template versions.
- [x] Research runs persist canonical strategy identity, engine version, data fingerprints, assumptions, and results.
- [x] Close-derived signals fill at the following session's open.
- [x] Trade-ledger prices and P&L use the same fill model as portfolio equity.
- [x] Benchmark alignment never backfills from future observations.
- [x] Buy-and-hold, SPY, cash, exposure-matched, and volatility-matched evidence is available; sector references are explicit relative-strength inputs.
- [x] One/two-parameter search is exhaustive and capped.
- [x] Three-to-six-parameter search uses seeded, capped Optuna TPE trials.
- [x] Walk-forward selection cannot inspect the untouched final window.
- [x] Heatmap, stability, performance-decay, and Deflated-Sharpe evidence is returned and rendered.
- [x] A single historical run cannot receive a Robust Candidate verdict.
- [x] SMA trend, RSI mean reversion, and Donchian breakout signals are future-data invariant.
- [ ] Validate Release 0.4 against several real tickers and market regimes before removing the development version suffix.

## Release 0.4.1 — Strategy Scope Correction

- [x] Catalogue strategy identity excludes ticker, universe, benchmark, timeframe, and execution assumptions.
- [x] Research runs persist a separate immutable research design and include it in reproducibility identity.
- [x] Existing V2 catalogue rows are scope-normalized and deduplicated during local application initialization.
- [x] Relative-strength templates support market, automatic-sector, and explicit-custom benchmark references.
- [x] Commission and slippage default to zero basis points with visible cost sensitivity retained.
- [x] Next-open buy-and-hold parity is tested for an always-long, zero-cost strategy.
- [x] Stock Strategy Lab Monte Carlo UI and API are removed; Option Lab paths remain available.

## Release 0.4.2 — Market Replay

- [x] Individual-stock research results include daily, weekly, monthly, and yearly OHLCV bars.
- [x] Every interval recomputes SMA 20, EMA 20, Bollinger 20/2σ, volume average 20, RSI 14, and MACD 12/26/9 without future observations.
- [x] Strategy Lab renders candlesticks, independent price-overlay toggles, linked volume and momentum panes, hover details, and entry/exit markers after the trade ledger.
- [x] Ranked portfolios explicitly omit candlesticks rather than constructing a misleading synthetic OHLC series.
- [x] Aggregation, future-data invariance, API shape, static assets, JavaScript syntax, and the full Python suite are automated.
- [ ] Complete manual visual checks for interval switching, overlay combinations, hover positioning, narrow layouts, and high-DPI displays before marking 0.4.2 stable.

## Release 0.4.3 — Strategy Research Canvas

- [x] Add Vite, React, TypeScript, Tailwind, and shadcn/ui without changing FastAPI contracts.
- [x] Keep natural-language, template, and catalogue selections mutually exclusive.
- [x] Replace permanent strategy forms with command search, quick starts, editable rule chips, and progressive disclosure.
- [x] Keep ticker, timeframe, assumptions, and the run action in one compact research context bar.
- [x] Require confirmation of normalized natural-language proposals before execution.
- [x] Validate provider-authored JSON and generate legacy YAML only on the server.
- [x] Preserve explicit risk and volume clauses in deterministic translation fallbacks.
- [x] Offer trailing-stop configuration with next-open fill semantics.
- [x] Distinguish single-stock relative strength from portfolio ranking in labels and help text.
- [x] Show Darvas and Fibonacci strategy rules on the financial chart.
- [x] Provide a direct return path from every legacy panel to the React research canvas.
- [x] Keep candlesticks, interval controls, strategy overlays, SMA/EMA/Bollinger/Darvas/Fibonacci toggles, volume, RSI, MACD, and markers visible in the research workspace.
- [x] Add evidence tabs for overview, equity/drawdown, trades, robustness, and assumptions.
- [x] Serve the React build at `/` when available and preserve the vanilla interface at `/legacy`.
- [x] Add frontend typechecking, component tests, production build validation, and Python source-contract coverage.
- [x] Complete keyboard and screen-reader source review, responsive DOM contracts, keyboard chart inspection, labelled live chart values, and reduced-motion handling.
- [ ] Complete a connected-browser visual sweep for narrow/high-DPI layouts, overlay combinations, focus appearance, and pointer hover before marking 0.4.3 stable.
- [ ] Port the remaining Stock Observatory and Market Pulse panels before retiring the vanilla fallback; Option Lab moved in 0.5.

## Release 0.5 — Option Lifecycle Canvas

- [x] Route Option Lab through the React application while preserving all V2 API contracts and the vanilla fallback.
- [x] Replace the position form with recipe cards and isolated editable leg cards.
- [x] Select every Yahoo-reported expiry, inspect every returned contract, load only the target leg, and retain manual assumptions during outages.
- [x] Keep interest, dividend, path-count, and seed assumptions behind progressive disclosure.
- [x] Render expiry payoff, price/time slices, scaled Greeks, and animated underlying and position-P&L paths.
- [x] Persist immutable simulation runs, linked paper positions, and complete lifecycle states in DuckDB.
- [x] List and reopen saved simulation runs and paper positions after a browser reload.
- [x] Journal hold, close, partial close, roll, share purchase/sale, added-leg, exercise, expiry, early assignment, and expiry assignment events.
- [x] Make Build, Explore, and Journal progression reflect actual application state.
- [x] Add typed frontend contracts, pure option-draft tests, component tests, and React source-contract checks.
- [ ] Complete connected-browser visual and keyboard checks for chain selection, narrow leg cards, scenario charts, and lifecycle side sheets.
- [ ] Reconcile golden lifecycle fixtures for every multi-leg close and roll combination before declaring 0.5 stable.
- [x] Complete expiry-aware chain selection and full-contract inspection from Product Backlog P0.1.
- [x] Complete Position Recipe V2 and Conversion validation from Product Backlog P0.2/P0.4.
- [x] Persist and reload immutable option simulation runs from Product Backlog P0.3.
- [x] Complete share-purchase and add-leg lifecycle transformations for the LEAP management playbook from Product Backlog P0.5.

## Release 0.6 — Observability Canvases

- [x] Add resilient V2 stock and market-overview contracts with row-level availability and provenance.
- [x] Port Stock Observatory to React with quote evidence, day/week/month/year candles, volume, momentum, technical overlays, and cached-data warnings.
- [x] Add expiry-aware current-option context without making stock evidence depend on option-provider success.
- [x] Add a browser-local, no-login watchlist for symbol navigation without representing it as holdings.
- [x] Port Market Pulse to React with sector breadth, daily movement, three-month SPY-relative strength, cross-asset proxies, and provider readiness.
- [x] Preserve unavailable market rows and their warnings while rendering successful current or cached rows.
- [x] Carry validated ticker symbols directly among Stock Observatory, Strategy Lab, and Option Lab.
- [x] Route all four primary laboratories through the lazy-loaded React shell while retaining `/legacy` as an explicit fallback.
- [x] Add API contracts, partial-provider tests, navigation/watchlist tests, component tests, and browser source guards.
- [ ] Complete connected-browser review across desktop, narrow, high-DPI, keyboard, chain-table, and provider-failure states.
- [ ] Retire the vanilla fallback only after the connected-browser parity gate is signed off.

## Release 0.7 — Company Intelligence Foundation

- [x] Add a stable company model keyed by `company_id` and normalized SEC CIK.
- [x] Separate time-bounded ticker/exchange mappings from company-business identity.
- [x] Resolve ticker and CIK lookups to the same canonical company record.
- [x] Persist companies and security mappings in backward-compatible DuckDB schema version 6.
- [x] Preserve prior mappings through explicit ticker changes and delisting transitions.
- [x] Persist source, observation, `known_at`, retrieval, cache, status, and warning context with identity records.
- [x] Add idempotent SEC ticker/CIK/exchange directory ingestion without claiming complete historical coverage.
- [x] Cover normalization, duplicate conflicts, metadata updates, history, delisting, SEC parsing, and database reopen behavior.
- [x] Complete INT-02 point-in-time SEC facts with accession deduplication, restatement retention, acceptance-aware `known_at`, as-of reads, and provider-cache fallback.
- [x] Complete INT-03 versioned concept precedence, unit normalization, annual/quarterly/TTM metrics, derivations, warnings, and source-fact lineage.
- [x] Complete INT-04 strict V3 company overview, fact-history, and normalized-metric contracts with canonical identity, provenance, as-of context, documentation, and contract tests.

## Release 0.8 — Valuation And Earnings Intelligence

- [x] Complete INT-05 historical point-in-time valuation with deterministic market-close alignment, TTM denominators, explicit `nm`, statistics, provenance, DuckDB caching, and restatement tests.
- [x] Complete INT-06 stable earnings events, source evidence, timing quality, trading-session windows, benchmark adjustment, volume context, deterministic persistence, and before/after/weekend/holiday/unknown tests.
- [x] Complete INT-07 Company Intelligence navigation, historical earnings table, selectable evidence detail, reported-versus-calculated distinction, aggregate sample sizes, keyboard chart, responsive source contracts, and non-predictive language.
- [x] Complete INT-08 provider-neutral revenue/EPS estimate observations, revision `known_at`, exact fiscal mapping, empty-safe API behavior, local fixtures, and expectation-versus-reported documentation.
- [x] Preserve all existing V2 contracts and strict V3 unknown-field rejection.
- [x] Reconcile synchronized NVIDIA evidence: 26,903 SEC facts produce 67 TTM periods, eight populated current valuation measures, and 40 source-backed earnings reactions.
- [x] Reconcile representative maximum-history performance: 1,439 weekly observations across eight valuation measures return in 4.5 seconds; the warm-cache 40-event earnings response returns in 3.8 seconds on the development machine.
- [ ] Complete connected-browser review using a locally synchronized supported company with live/cached Yahoo and SEC data.

## Release 0.9 — Evidence And Business Network

- [x] Complete INT-09 strict models for versioned evidence documents, exact source spans, parse status, and typed claim links.
- [x] Persist INT-09 records in backward-compatible DuckDB schema version 10 without rewriting existing company, market, research, or option records.
- [x] Deduplicate exact source content and retain changed content as a linked document version.
- [x] Enforce company ownership and `known_at` boundaries for document, span, and claim-evidence reads.
- [x] Prevent failed document parsing from creating unsupported evidence spans.
- [x] Expose read-only strict V3 document, detail, span, and claim-evidence contracts with incomplete-coverage warnings.
- [x] Cover duplicate ingestion, changed documents, as-of filtering, independent span retrieval, multiple spans per claim, parser failure, migration, and API source traceability.
- [x] Add permitted public-document collectors and deterministic parsing workflows for supported companies.
- [x] Complete INT-10 source-backed customer/supplier relationship persistence and deterministic extraction, including unresolved counterparties, evidence accumulation, history, and audited overrides.
- [x] Complete INT-11 interactive company relationship graph with direction, filters, keyboard-accessible table fallback, focused navigation, evidence/history dialogs, and incomplete-disclosure context.
- [x] Complete INT-12 versioned segment, geography, and company-specific KPI intelligence with reorganization boundaries, compatible comparisons, source evidence, and explicit missing coverage.
- [x] Complete INT-13 immutable guidance and management-commitment history with linked revisions, original wording, normalized ranges, evidence, and rule-based outcomes.
- [x] Complete connected-browser review of evidence context, resolved and unresolved business-network navigation, responsive graph overflow, keyboard interaction, source history, and explicit incomplete-disclosure states.

## Release 0.10 — Personal Research Completion

### INT-18 — Public Document Collection

- [x] Discover supported SEC filings, filing indexes, primary documents, and relevant EX-99 exhibits with acceptance-aware `known_at`.
- [x] Persist verified raw source content, parser versions, append-safe evidence versions, refresh runs, and per-document diagnostics.
- [x] Parse HTML, XHTML, XML, plain text, inline-XBRL dimensions, and custom-taxonomy facts without executing source code.
- [x] Populate relationships, operating disclosures, and guidance only through inspectable evidence spans.
- [x] Distinguish no disclosure, provider failure, unsupported format, parser failure, and extraction failure.
- [x] Add idempotent refresh, provider throttling/retries, progress, cancellation, source health, strict API contracts, CLI commands, and React Sources controls.
- [x] Cover realistic SEC fixtures, dimensional/custom facts, source-backed extraction, repeated refreshes, cancellation, migration, local jobs, and browser-component behavior.
- [x] Reconcile a bounded live SEC refresh for NVDA and inspect the resulting Company Intelligence source health in a connected browser.

### Remaining 0.10 Work

- [x] Complete INT-14, INT-16, and INT-17 Company Intelligence consolidation, independent time controls, event charts, and semantic visual hierarchy.
- [x] Complete INT-15 provider-neutral S&P 500 snapshots, resilient bulk jobs, resume/retry, and coverage diagnostics.
- [x] Complete MKT-01 sector constituent treemap drill-down.
- [x] Complete STR-01 Idea → Backtest → Current Signal.
- [x] Complete OPT-01 Options Planner Plan → Compare → Scenario.
- [x] Start option planning from ticker, outlook, horizon, optional target/range, share context, acceptable loss, and capital budget.
- [x] Compare only existing Pydantic-validated structures with debit/credit, capital/collateral, maximum loss/gain, break-even, expiry/strikes, aggregate Greeks, bid/ask quality, and plain-language trade-offs.
- [x] Exclude uncovered short calls from normal suggestions; gate covered calls and cash-secured puts on explicit share context.
- [x] Price the primary future price/date scenario on the server and expose value, P&L, remaining time, break-even relation, Greeks, assumptions, provenance, and warnings.
- [x] Preserve plan context while opening the existing leg builder; keep full simulation and DuckDB journal optional and backward compatible.
- [x] Add source-preserving historical earnings movement and selected-expiry straddle context without a forecast or mispricing claim.
- [x] Cover bullish, bearish, neutral, owned-share, acquire-share, low-budget, quote direction, provider-context failure, API, keyboard, narrow-layout, and live NVDA workflows.
- [x] Run the integrated Release 0.10 unit, integration, contract, frontend, browser, and real-data acceptance sweep.
- [x] Pass 164 Python tests, 50 frontend tests, Python lint, TypeScript typecheck, production build, and `git diff --check` on the integrated branch.
- [x] Complete connected-browser flows for Company Intelligence, intelligence refresh, S&P 500/sector drill-down, Strategy Current Signal, and live NVDA option planning/scenarios, including narrow layouts and no console errors.

## Deferred Launch Stability — Former Release 0.3 Gates

Run these when preparing an actual public release candidate:

- [ ] Back up a real existing `data/gbb_terminal.duckdb`, migrate the copy, and reconcile table/record counts.
- [ ] Install from a clean Python environment and launch from outside the repository directory.
- [ ] Exercise every primary browser action on supported desktop viewport sizes.
- [ ] Verify Google AI Studio, OpenAI, Anthropic, and deterministic fallback using deliberately non-secret test accounts.
- [ ] Simulate Yahoo/provider outage, quota exhaustion, stale-cache fallback, and offline restart.
- [ ] Verify log rotation and confirm secrets/instructions are not written to logs.
- [ ] Run Linux and macOS CI; add Windows only when Windows support is declared.
- [ ] Complete accessibility keyboard, focus, contrast, and reduced-motion checks.
- [ ] Record known limitations and recovery steps in release notes.
- [ ] Tag the release only after the checklist is signed off against the exact commit.
