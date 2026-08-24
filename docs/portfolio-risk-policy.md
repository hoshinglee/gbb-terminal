# Personal Portfolio Context And Risk Policy

## Business Definition

Personal Portfolio Context is the local capital and holdings record used by future Decision Center workflows. It answers how much capital is investable, how much cash is liquid, and which positions already exist before a stock or option instrument is considered.

Risk Policy is a reusable set of explicit portfolio limits. It is evidence for later sizing and risk checks, not an automated recommendation, order instruction, or brokerage control. Existing Strategy Lab, Option Lab, Market Pulse, and Company Intelligence workflows remain available when no portfolio context or policy has been configured.

## Domain Boundary

- Portfolio context owns investable value, liquid cash, base currency, and manual holdings.
- Risk policy owns reusable position, assignment, collateral, cash-reserve, and stress-loss limits.
- Strategy definitions continue to own only declarative trading rules and risk parameters intrinsic to that strategy.
- Research designs continue to own ticker, universe, timeframe, benchmarks, and execution assumptions.
- Option positions and their lifecycle ledger remain separate paper simulations. They do not silently update personal holdings.

This separation enforces the product rule that desired position size is decided before instrument choice.

## Portfolio Context

The initial local context is single-user and uses the stable key `personal`. It records:

- Investable portfolio value.
- Liquid or available cash, which cannot exceed investable value.
- USD as the initial base currency.
- Manual positions with ticker, signed share quantity, non-negative cost basis per share, optional signed manual market value, and notes.

Manual values are authoritative user context. Market-data refresh failures cannot delete or overwrite them. Negative shares and market values are permitted so a manually entered short position remains representable.

When a holding is saved, the service resolves its normalized ticker through the existing time-bounded Company Intelligence identity registry. A successful match stores the stable `company_id`; otherwise the normalized ticker remains available with an explicit `unresolved` identity status. Identity resolution does not require a market price.

## Risk Policy

The initial reusable policy key is `personal-default`. Every policy version contains:

- Normal target position percentage.
- Maximum single-name exposure percentage.
- Maximum assignment exposure percentage.
- Maximum short-option collateral exposure percentage.
- Minimum unencumbered cash reserve as a percentage, an amount, or both.
- Portfolio stress-loss ceiling percentage.

Normal target position cannot exceed maximum single-name exposure. Percentages are validated within zero-to-one-hundred bounds, with exposure ceilings greater than zero. At least one cash-reserve form is required.

Saving a changed policy inserts a new immutable version and links it to the superseded policy. It never rewrites the previous version. A snapshot stores the complete validated policy payload, policy identity, and version so a future research run or decision record can attach the exact policy state that existed at that time.

## Browser Workflow

Use **Portfolio & Risk** in the global application shell. The compact side sheet contains:

1. **Capital:** define investable value and liquid cash.
2. **Risk Policy:** define or revise the reusable limits and create an immutable snapshot.
3. **Holdings:** create, edit, and delete manual existing positions.

The shell summary shows only the current maximum position, cash reserve, and stress ceiling so the policy remains visible without dominating the research canvases. Internal IDs, version keys, and snapshot payloads are not exposed in the ordinary workflow.

## API Workflow

1. Save capital with `PUT /api/v2/portfolio-context`.
2. Add manual holdings with `POST /api/v2/portfolio-context/positions`.
3. Save a policy with `PUT /api/v2/risk-policy`; each subsequent save creates the next version.
4. Freeze the current policy with `POST /api/v2/risk-policy/snapshots`.
5. Read the exact snapshot later with `GET /api/v2/risk-policy/snapshots/{snapshot_id}`.

The combined `GET /api/v2/portfolio-context` response is optional by design: a new installation returns no capital context, no policy, and an empty holdings list rather than blocking another lab.

## Storage And Compatibility

DuckDB schema version 17 appends `portfolio_contexts`, `portfolio_positions`, `risk_policies`, and `risk_policy_snapshots`. Existing databases are migrated in place. No existing strategy, research, company, option, market-data, or evidence tables are rewritten.

The tables include nullable `owner_id` only where future hosted ownership may be introduced. Current domain behavior remains local and single-user, with no authentication dependency.

## Non-Goals

- Brokerage synchronization or order execution.
- Automatic recommendations or claims that a limit is suitable.
- Institutional VaR, risk-factor, or regulatory capital models.
- Automatic mutation of holdings from market prices or paper option events.
