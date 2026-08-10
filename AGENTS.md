# GBB Terminal Agent Guide

## Product Boundaries

- Keep GBB Terminal free, open-source, local-first, and single-user by default.
- Support US equity and options research and paper simulation only. Never add live brokerage execution without an explicit product decision.
- Treat results as educational research evidence, not investment advice or claims of superior returns.
- Keep stock research and Option Lab as separate first-class domains.

## Domain Boundaries

- Keep strategy logic separate from where and how it is tested.
- A strategy definition contains declarative rules, required datasets, parameter specifications, and a version.
- A strategy configuration contains only selected rule and risk parameter values. Its identity must not depend on ticker, benchmark, universe, dates, or execution costs.
- A research design contains ticker or selection universe, timeframe, benchmarks, validation split, and execution assumptions.
- A research run is immutable and records a strategy configuration, research design, data snapshots, engine version, and results.
- Catalogue deduplication is based on canonical strategy configuration, not display names or research scope. Keep semantic keys internal.
- Key Company Intelligence by stable `company_id` and normalized CIK, never by ticker alone.
- Treat ticker and exchange as time-bounded security mappings. Ticker changes, additional share classes, and delistings must not overwrite company history.
- Keep V2 stock-price and option workflows ticker-based; resolve into `company_id` only when entering the Company Intelligence domain.

## Research Integrity

- Use declarative, schema-validated strategy rules only. Never execute user- or LLM-generated Python, expressions, or YAML.
- Evaluate signals only from information known at the time. Apply next-session execution unless a documented alternative is selected.
- Preserve source, retrieval time, observation time, and `known_at` timestamps where data supports them.
- Compare strategies transparently against buy-and-hold, cash, and appropriate selected benchmarks. Keep underperformance visible.
- Report return alongside drawdown, exposure, turnover, trade count, costs, and downside-adjusted metrics.
- Keep an untouched final test window for parameter search and record all attempted configurations.
- Make every automatic sector, peer, benchmark, or data-quality decision visible and overridable. Do not silently infer peers.

## Data, Storage, And Configuration

- Use DuckDB for local runtime storage. Never commit `data/`, `log/`, secrets, or downloaded market data.
- Resolve runtime paths through `gbb_terminal.settings`, independent of the current working directory.
- Keep provider adapters isolated behind shared interfaces and retain cache, retry, rate-limit, and stale-data behavior.
- Keep provider configuration in `conf/` and secrets in environment variables or `.env`; commit only `.env.example`.
- LLM providers may propose validated strategy payloads only. Provider selection must support configured Google AI Studio, OpenAI, and Anthropic/Claude adapters without coupling domain logic to a vendor.

## User Experience

- Hide internal hashes, YAML, and implementation details from standard views. Offer them only through an explicit Advanced or Export flow.
- Use clear labels that distinguish strategy parameters, research settings, comparison benchmarks, and portfolio-selection universes.
- Default to simple, honest assumptions. If costs are zero, state that the results use a zero-cost assumption and expose sensitivity analysis.
- Do not show a research tool merely because it is technically available; retain only tools with a clear decision-making purpose.

## Engineering And Documentation

- Preserve public API paths and response contracts during structure-only refactors.
- Keep backend modules under `src/gbb_terminal` and browser assets under `app/`.
- Prefer small, focused changes. Do not combine refactors with product behavior changes unless explicitly requested.
- Add or update unit, integration, contract, and browser tests appropriate to the changed behavior.
- Update relevant documentation in `docs/` whenever domain behavior, configuration, APIs, or user workflows change.
- Make logical, reviewable commits and do not commit generated data, logs, secrets, or local environment files.
