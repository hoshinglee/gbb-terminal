# Backtesting

## Business definition

Backtesting estimates how a precisely defined rule would have behaved under explicit assumptions. It does not establish that future returns will match historical evidence.

## Execution

`apply_execution(frame, assumptions)` shifts signals by one session, applies commission and slippage on position turnover, accrues configured cash return, and calculates strategy equity. Signals never receive same-session fills.

## Evidence

`run_research_backtest()` compares strategy equity with the underlying, SPY or a selected benchmark, cash, and an exposure-matched passive series. It returns OHLCV-aligned hover data, indicator values, trades, and metrics including CAGR, Sharpe, Sortino, Calmar, drawdown, time underwater, volatility, exposure, turnover, win rate, and profit factor.

`evidence_verdict()` assigns one plain-language label: Robust Candidate, Promising But Unstable, Insufficient Evidence, or Does Not Justify Complexity. The label is explanatory, not investment advice.

## Search and portfolios

`run_parameter_search()` supports one to six parameters, exhaustive grids for one or two dimensions, capped deterministic search for larger spaces, walk-forward scoring, and an untouched final window. Every accepted or rejected attempt is returned.

Each search creates a `local_jobs` record before execution. Progress, completion output, failure, and cancellation intent are persisted. `GET /api/v2/jobs/{id}` and `POST /api/v2/jobs/{id}/cancel` keep the local interface replaceable by hosted workers later.

`run_ranked_portfolio()` ranks a user universe by trailing return, holds the top names at equal weight, rebalances on schedule, and compares against equal-weight peers and the selected benchmark.
