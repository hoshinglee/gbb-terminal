# Release Readiness

This checklist separates research correctness from launch-environment stabilization. Release 0.4 may continue without prematurely treating local-machine launch checks as complete.

## Release 0.4 — Research Credibility

- [x] Canonical Strategy Model V2 rejects unknown fields and stale template versions.
- [x] Research runs persist canonical strategy identity, engine version, data fingerprints, assumptions, and results.
- [x] Close-derived signals fill at the following session's open.
- [x] Trade-ledger prices and P&L use the same fill model as portfolio equity.
- [x] Benchmark alignment never backfills from future observations.
- [x] Buy-and-hold, SPY, sector, peers, cash, exposure-matched, and volatility-matched evidence is available.
- [x] One/two-parameter search is exhaustive and capped.
- [x] Three-to-six-parameter search uses seeded, capped Optuna TPE trials.
- [x] Walk-forward selection cannot inspect the untouched final window.
- [x] Heatmap, stability, performance-decay, and Deflated-Sharpe evidence is returned and rendered.
- [x] A single historical run cannot receive a Robust Candidate verdict.
- [x] SMA trend, RSI mean reversion, and Donchian breakout signals are future-data invariant.
- [ ] Validate Release 0.4 against several real tickers and market regimes before removing the development version suffix.

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
