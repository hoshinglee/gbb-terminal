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
- [ ] Complete INT-02 point-in-time SEC financial fact storage.
- [ ] Complete INT-03 normalized financial metrics.
- [ ] Complete INT-04 V3 Company Intelligence contracts before adding the browser workflow.

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
