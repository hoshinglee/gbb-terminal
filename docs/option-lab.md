# Option Lab

## Business definition

Option Lab answers: “If I enter this paper position, how may value and exposure change, and what choices exist before expiry?” It never sends orders.

## Supported positions

Long and short calls/puts, covered calls, cash-secured puts, bull/bear call/put vertical spreads, and a matched conversion are available. Users may initialize legs from a selected-expiry Yahoo snapshot or enter assumptions manually.

## Pricing and simulation

- `american_option_price()` uses a Cox-Ross-Rubinstein tree with early exercise.
- `black_scholes_price()` provides a secondary European educational comparison.
- `option_greeks()` calculates finite-difference delta, gamma, theta, and vega from the American model.
- `simulate_position()` returns expiry payoff, price/time P&L surfaces, probability estimates, Greeks, and Monte Carlo underlying/position paths.

## Lifecycle accounting

`initial_state()` records premium cash flow, shares, collateral, open legs, and the originating immutable simulation-run ID. `apply_event()` handles hold, full or partial close, strike/expiry roll, share purchases and sales, validated added legs, exercise, out-of-the-money expiry, and early/expiry assignment. Every API event stores both its payload and complete resulting state in DuckDB. Assignment or exercise keeps the ledger open whenever shares or another option leg remain.

Historical results are labelled **Theoretical Simulation** because free providers do not supply dependable historical contract marks. Daily local snapshots gradually build prospective history.

## React workflow

Release 0.5 exposes Option Lab at `/?lab=options` as a three-stage canvas:

1. **Build:** choose one of eleven research recipes, edit each leg, or follow **Target Leg → Expiry → Contract** to load a current Yahoo contract. Every provider-reported expiry and every returned call or put for that expiry remain inspectable.
2. **Explore:** persist and simulate the exact position, then inspect expiry payoff, price/time slices, scaled Greeks, American and European model values, animated paths, entry cash profile, and explicit lifecycle branches.
3. **Journal:** save a paper position linked to that immutable run, then record hold, close, partial close, roll, share purchase/sale, added-leg, exercise, expiry, and assignment decisions.

Ticker, spot, position recipe, and the primary simulation action stay in the compact context bar. Interest rate, dividend yield, modeled-path count, and random seed use a progressive-disclosure side sheet. Selecting a different recipe replaces the earlier leg state instead of retaining incompatible values.

Current-chain selection is optional. Manual strike, premium, IV, expiration, and quantity remain first-class inputs so the application stays useful during provider outages. Long contracts use the displayed ask and short contracts use the displayed bid by default; last or midpoint fallbacks are labelled. Loading a chain also refreshes the observed underlying close through the existing chart-data API, while source time, delay, quote quality, spread, volume, open interest, and warnings remain visible.

Every `POST /api/v2/options/simulations` call creates an immutable DuckDB run containing its validated request, complete result, model version, creation time, and market-data provenance. The Runs sheet can reload an earlier scenario without rewriting it. The Positions sheet reopens any persisted paper ledger and restores its linked run when available. Editing a loaded draft clears the active evidence and ledger view but leaves both stored records unchanged.

Conversion evidence separates idealized put-call-parity terminal proceeds from executable return. The result includes capital committed, premium debit/credit, holding period, configured cash-rate comparison, and warnings for financing, dividends, early assignment, taxes, fees, and corporate actions. A short-call playbook exposes alternatives—remain naked, buy actual-price shares, add a higher call, roll, or add a separately collateralized put—without presenting one branch as a recommendation.

The Build, Explore, and Journal progress rail derives its active state from actual simulation and ledger state. It is not a decorative step indicator.

## Browser modules

- `app/web/src/features/option-lab/option-lab.tsx`: request orchestration and canvas progression.
- `option-presets.ts`: pure template-to-leg construction, contract application, and client validation.
- `position-builder.tsx`: position recipes, editable leg cards, and current-chain side sheet.
- `scenario-workspace.tsx`: payoff, time slices, paths, Greeks, and model boundaries.
- `lifecycle-workspace.tsx`: DuckDB paper-position creation and lifecycle event journal.
- `simulation-history-sheet.tsx`: immutable local run history and reload workflow.
- `option-line-chart.tsx`: responsive pointer- and keyboard-inspectable scenario charts.

Python scenario interpretation lives in `src/gbb_terminal/options/analysis.py`; recipe validation and lifecycle accounting remain in the domain package rather than the browser.

The frontend calls the existing V2 option endpoints; pricing and accounting remain Python domain responsibilities.
