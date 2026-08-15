# Architecture

## Business boundary

GBB Terminal is an educational research workbench, not an execution system, broker, adviser, or source of guaranteed returns. Stock Strategy Lab and Option Lab are independent domain products that share market data, storage, settings, and observability.

## Runtime layout

- `app/web/`: Vite, React, TypeScript, shadcn/ui source for all five research canvases.
- `app/static/react/`: ignored production build output served by FastAPI when present.
- `app/index.html` and `app/static/*.js`: retained vanilla migration fallback; primary navigation no longer depends on it.
- `src/gbb_terminal/api/`: FastAPI application, schemas, and route groups.
- `src/gbb_terminal/strategy/`: strategy contracts, templates, safe factory, and indicators.
- `src/gbb_terminal/backtesting/`: signal execution, costs, metrics, parameter search, and portfolio ranking. Option-specific scenario paths remain under `options/`.
- `src/gbb_terminal/options/`: option contracts, American pricing, scenario simulation, strategy templates, and lifecycle transitions.
- `src/gbb_terminal/intelligence/`: canonical company identity, financial/earnings analysis, versioned evidence documents and spans, and source-backed business intelligence.
- `src/gbb_terminal/market_data/`: provider-neutral service and public provider adapters.
- `src/gbb_terminal/storage/`: DuckDB system of record.
- `src/gbb_terminal/llm/`: optional language-model translation only.
- `src/gbb_terminal/observability/`: application logging.
- `conf/`: checked-in configuration examples and ignored local runtime configuration.

`gbb_terminal.settings` resolves frontend, data, log, and configuration paths from the installed source location. `conf/app.yaml` holds non-secret local settings; `.env` holds secrets. Process environment variables and `.env` override YAML settings, so the server does not depend on its current working directory.

The root route selects `app/static/react/index.html` only when a production frontend build exists. `/legacy` always serves `app/index.html`. Both paths share the same FastAPI contracts and DuckDB records, so React migration does not fork domain behavior or persistence.

## Request flow

1. A route validates a Pydantic request.
2. Market data is loaded from a fresh DuckDB cache or a provider.
3. Provider failure falls back to stale local data when available and adds visible warnings.
4. A domain service calculates signals, research evidence, or an option state transition.
5. Immutable research or ledger records are persisted.
6. The API returns data plus assumptions and provenance for browser rendering.

The React Strategy Lab keeps one reducer-backed research workspace. Natural-language, template, and catalogue selections are mutually exclusive, preventing stale template parameters from surviving a selection change. The React Option Lab keeps position-draft, chain-snapshot, simulation, and persisted-ledger state separate so editing an assumption cannot silently mutate an earlier journal state. Stock Observatory separates selected symbol/window, OHLCV evidence, and current option-chain context. Market Pulse accepts partial rows so one public-symbol outage cannot erase every available sector or macro observation. Company Intelligence loads identity, normalized financials, valuation, earnings, relationships, operations, and guidance into separate typed response states with `Promise.allSettled`, so one unavailable dataset does not erase successful evidence. Lightweight Charts owns market and event series; accessible SVG owns numeric option scenarios and the one-hop network; shadcn/ui owns interaction components, progressive disclosure, and evidence navigation.

Cross-lab links carry only a validated ticker in the URL. Strategy rules, option legs, model assumptions, and research results are never encoded into navigation state. The Stock watchlist is browser-local navigation metadata and is not an authenticated portfolio or DuckDB research record.

Company Intelligence has a separate identity boundary. Price and option requests continue using normalized tickers, while business-data consumers resolve that security through `CompanyIdentityService` into a stable `company_id`. CIK identifies the SEC filer; ticker/exchange mappings carry validity periods so ticker changes, alternate share classes, and delistings cannot rewrite company history. Evidence documents then attach to the durable company rather than a mutable ticker. See [Company Intelligence](company-intelligence.md).

Point-in-time Company Facts are persisted independently from normalized metrics. `FinancialFactService` owns SEC ingestion, source identity, acceptance-aware `known_at`, and as-of retrieval. `NormalizedMetricsService` owns versioned concept precedence, unit conversion, annual/quarterly/TTM construction, derived calculations, warnings, and source-fact lineage. API routes do not perform financial normalization.

`CompanyIntelligenceService` is the V3 orchestration boundary. The router only validates strict query models, maps typed domain results to explicit camelCase response schemas, and translates lookup/validation failures into HTTP semantics. No Company Intelligence calculation is implemented inside API routes, and V2 stock/option route contracts remain unchanged.

`EvidenceService` is the source-traceability boundary underneath that orchestrator. `EvidenceRepository` versions public documents, preserves exact source spans, and links those spans to typed claims. Relationship, segment, KPI, and guidance modules may depend on this layer, but they may not persist a sourced claim without inspectable evidence. See [Evidence Intelligence](evidence-intelligence.md).

`RelationshipService` owns conservative explicit-text extraction, counterparty resolution, perspective direction, current-network reads, and auditable overrides. `OperationsIntelligenceService` owns version-aware mix and growth, while `GuidanceService` owns immutable revisions and deterministic outcome reconciliation. Their repositories persist domain records and generic evidence links; API routes only validate and serialize. See [Business Network](business-network.md), [Operating Intelligence](operating-intelligence.md), and [Guidance Intelligence](guidance-intelligence.md).

Hosted authentication is intentionally absent. Storage tables allow nullable `owner_id` so repository logic can later support users without contaminating domain models.

See [System Diagrams](system-diagrams.md) for runtime, frontend state, request sequence, DuckDB, and build-fallback views.
