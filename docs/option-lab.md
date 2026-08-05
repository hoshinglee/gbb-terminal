# Option Lab

## Business definition

Option Lab answers: “If I enter this paper position, how may value and exposure change, and what choices exist before expiry?” It never sends orders.

## Supported positions

Long and short calls/puts, covered calls, cash-secured puts, and bull/bear call/put vertical spreads are available. Users may initialize legs from a current Yahoo snapshot or enter assumptions manually.

## Pricing and simulation

- `american_option_price()` uses a Cox-Ross-Rubinstein tree with early exercise.
- `black_scholes_price()` provides a secondary European educational comparison.
- `option_greeks()` calculates finite-difference delta, gamma, theta, and vega from the American model.
- `simulate_position()` returns expiry payoff, price/time P&L surfaces, probability estimates, Greeks, and Monte Carlo underlying/position paths.

## Lifecycle accounting

`initial_state()` records premium cash flow, shares, collateral, and open legs. `apply_event()` handles hold, full or partial close, strike/expiry roll, exercise, out-of-the-money expiry, and early/expiry assignment. Every API event stores both its payload and complete resulting state in DuckDB.

Historical results are labelled **Theoretical Simulation** because free providers do not supply dependable historical contract marks. Daily local snapshots gradually build prospective history.

