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

Implementation status: INT-01 and INT-02 are implemented on the Release 0.7 branch. INT-03 and INT-04 remain required before the Release 0.7 exit criteria are complete.

### INT-01 — Canonical Company Identity

- Persist stable company identity by `company_id` and normalized CIK.
- Resolve active or historical ticker mappings to the same company.
- Preserve ticker changes, alternate share classes, and delistings as dated security mappings.
- Ingest the official SEC ticker/CIK/exchange directory with explicit source limitations and retrieval context.

### Remaining Release 0.7 Foundations

- INT-03: normalized annual, quarterly, and TTM financial metrics.
- INT-04: dedicated V3 Company Intelligence APIs and explicit response schemas.

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
