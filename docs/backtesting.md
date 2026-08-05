# Backtesting

## Business definition

Backtesting estimates how a precisely defined rule would have behaved under explicit assumptions. It does not establish that future returns will match historical evidence. A single historical run can never receive the **Robust Candidate** verdict; that label requires untouched holdout evidence, nearby-parameter stability, and selection-adjusted support.

## Execution model

`apply_execution(frame, assumptions)` observes target positions after a session closes and fills changes at the next session's open. The old position receives the overnight return into that open; the new position receives the open-to-close return after execution. Commission and slippage apply to one-way turnover, and cash accrues only while the strategy remains uninvested.

Trade-ledger entry and exit prices use those same next-open fills. Dollar P&L is based on the run's initial capital and includes configured entry/exit costs. Open trades are marked at the final close.

Benchmark and peer histories are forward-filled only after their first known observation. They are never backfilled from a future observation. Every displayed equity series is rebased to `1.0` on the exact common evaluation start.

## Evidence

`run_research_backtest()` returns:

- Underlying buy-and-hold, selected benchmark, SPY, optional sector ETF, optional equal-weight peers, cash, exposure-matched, and volatility-matched comparisons.
- Total return, CAGR, excess return, Sharpe, Sortino, Calmar, drawdown, time underwater, volatility, exposure, turnover, cost sensitivity, trade count, win rate, and profit factor.
- Per-benchmark return, CAGR, drawdown, and volatility.
- Exact evaluation dates, execution assumptions, aligned hover data, indicators, fills, trades, regimes, and visible quality warnings.

`evidence_verdict()` assigns one plain-language label: Robust Candidate, Promising But Unstable, Insufficient Evidence, or Does Not Justify Complexity. The label is explanatory, not investment advice.

## Guarded parameter search

`run_parameter_search()` supports one to six parameters:

- One or two parameters use an exhaustive grid and reject a grid larger than the configured cap.
- Three to six parameters use a seeded Optuna TPE study with capped trials.
- Candidate selection uses only expanding walk-forward windows before the final boundary.
- The selected strategy runs once on the untouched final window.
- Every completed or rejected trial is recorded.

The response includes validation-window dates, median walk-forward Calmar scores, a parameter heatmap, nearby-parameter stability region, performance decay, Deflated-Sharpe probability, and an overfitting warning. Mutating final-window prices cannot change the selected parameters or development attempts.

Each search also persists its selected `StrategyInstance`, every attempted configuration, final result, data fingerprints, engine version, and reproducibility key as a `ResearchRun`.

## Ranked portfolios

`run_ranked_portfolio()` ranks a user universe by trailing return, holds the strongest names at equal weight, and fills scheduled rebalances at the following session's open. It reports both signal and execution dates and compares against equal-weight peers plus the selected and risk-matched benchmarks.
