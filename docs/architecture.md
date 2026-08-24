# Architecture

## Business boundary

GBB Terminal is an educational research workbench, not an execution system, broker, adviser, or source of guaranteed returns. Stock Strategy Lab and Option Lab are independent domain products that share market data, storage, settings, and observability. Decision Center connects company evidence to user-owned portfolio decisions without moving company scope into reusable strategy definitions.

## Runtime layout

- `app/web/`: Vite, React, TypeScript, shadcn/ui source for all five research canvases.
- `app/static/react/`: ignored production build output served by FastAPI when present.
- `app/index.html` and `app/static/*.js`: retained vanilla migration fallback; primary navigation no longer depends on it.
- `src/gbb_terminal/api/`: FastAPI application, schemas, and route groups.
- `src/gbb_terminal/strategy/`: strategy contracts, templates, safe factory, and indicators.
- `src/gbb_terminal/backtesting/`: signal execution, costs, metrics, parameter search, and portfolio ranking. Option-specific scenario paths remain under `options/`.
- `src/gbb_terminal/options/`: option contracts, deterministic planner selection, American pricing, scenario simulation, strategy templates, and lifecycle transitions.
- `src/gbb_terminal/portfolio/`: local capital context, manual holdings, immutable risk-policy versions, and policy snapshots.
- `src/gbb_terminal/decision_center/`: versioned theses and entry plans, position intent, instrument-fit/stress arithmetic, and decision journal snapshots.
- `src/gbb_terminal/intelligence/`: canonical company identity, financial/earnings analysis, versioned evidence documents and spans, and source-backed business intelligence.
- `src/gbb_terminal/market_data/`: provider-neutral service and public provider adapters.
- `src/gbb_terminal/universe/`: current research-universe snapshots, resilient bulk preparation, and sector constituent reads.
- `src/gbb_terminal/storage/`: DuckDB system of record.
- `src/gbb_terminal/llm/`: optional language-model translation only.
- `src/gbb_terminal/observability/`: application logging.
- `conf/`: checked-in configuration examples and ignored local runtime configuration.

`gbb_terminal.settings` resolves frontend, data, log, and configuration paths from the installed source location. `conf/app.yaml` holds non-secret local settings; `.env` holds secrets. Process environment variables and `.env` override YAML settings, so the server does not depend on its current working directory.

The root route selects `app/static/react/index.html` only when a production frontend build exists. `/legacy` always serves `app/index.html`. Both paths share the same FastAPI contracts and DuckDB records, so React migration does not fork domain behavior or persistence.

Personal portfolio context is an optional global domain, not a prerequisite for a laboratory. `PortfolioService` owns capital, manual holdings, company-identity resolution, policy versioning, and snapshots. The compact app-shell sheet reads and writes this domain without injecting portfolio assumptions into strategy definitions, research designs, or option lifecycle state. Manual holdings remain available during market-data outages because their quantities, basis, and optional market value are user-authored records rather than derived quote caches. See [Personal Portfolio Context And Risk Policy](portfolio-risk-policy.md).

Decision Center is a company-scoped orchestration domain. `DecisionCenterService` resolves canonical company identity and joins user-owned thesis versions, portfolio context, risk-policy versions, validated Option Lab structures, entry plans, stress results, and journal snapshots. `DecisionCenterEngine` owns arithmetic and policy statuses; the route may fetch a current quote or option chain but does not calculate fit. Strategy rules, Option Lab paper accounting, and Company Intelligence evidence remain their own systems of record. See [Decision Center](decision-center.md).

## Request flow

1. A route validates a Pydantic request.
2. Market data is loaded from a fresh DuckDB cache or a provider.
3. Provider failure falls back to stale local data when available and adds visible warnings.
4. A domain service calculates signals, research evidence, or an option state transition.
5. Immutable research or ledger records are persisted.
6. The API returns data plus assumptions and provenance for browser rendering.

Decision journal creation is a specialized immutable flow: the service copies the selected current thesis, risk policy, position intent, expression, and entry plan into a stable record. Subsequent edits append journal revisions and never mutate the earlier component snapshots. Process quality and later outcome remain separate fields.

The React Strategy Lab keeps one reducer-backed research workspace. Natural-language, template, and catalogue selections are mutually exclusive, preventing stale template parameters from surviving a selection change. Its Current Signal panel renders the final target/executed state, causal indicator values, and latest transition returned by the same Python signal and next-open execution frame as the historical run; there is no browser signal calculator. The React Option Lab keeps planner inputs/comparison/scenario, detailed position draft, chain snapshot, immutable simulation, and persisted ledger state separate. A candidate embeds the existing validated simulation request, and the server alone prices the primary future price/date scenario. Editing a draft cannot silently mutate an earlier comparison, simulation, or journal state. Market Pulse accepts partial rows so one public-symbol outage cannot erase every available sector or macro observation, and its separate universe job prepares current constituent research without converting membership into historical backtest evidence. Company Intelligence is the canonical individual-stock canvas and composes ticker-based quote/OHLCV evidence with company-based identity, annual/quarterly/TTM metrics, valuation, earnings, relationships, operations, guidance, and source health through separate typed states and `Promise.allSettled`. One unavailable dataset therefore does not erase successful evidence. Lightweight Charts owns event and valuation series; accessible SVG owns numeric option scenarios, constituent treemaps, and the one-hop network; shadcn/ui owns interaction components, progressive disclosure, and evidence navigation.

`options/planner.py` is a deterministic domain adapter around the existing engines. It selects a provider-reported expiry, chooses chain contracts through declared strike rules, applies ask-to-buy/bid-to-sell quote direction, validates every candidate as `OptionSimulationRequest`, and derives comparison/scenario evidence from `simulation.py`. It never generates a new strategy class, invokes an LLM, or permits an uncovered short-call candidate. `api/routes/options.py` owns only provider orchestration and optional Company Intelligence enrichment; earnings-provider failure is isolated as a plan warning.

Cross-lab links carry only a validated ticker in the URL. Strategy rules, option legs, model assumptions, and research results are never encoded into navigation state. The Company Intelligence watchlist is browser-local navigation metadata and is not an authenticated portfolio or DuckDB research record. Legacy `lab=stock` URLs canonicalize to `lab=intelligence` without copying or mutating research state.

Company Intelligence has a separate identity boundary. Price and option requests continue using normalized tickers, while business-data consumers resolve that security through `CompanyIdentityService` into a stable `company_id`. CIK identifies the SEC filer; ticker/exchange mappings carry validity periods so ticker changes, alternate share classes, and delistings cannot rewrite company history. Evidence documents then attach to the durable company rather than a mutable ticker. See [Company Intelligence](company-intelligence.md).

Point-in-time Company Facts are persisted independently from normalized metrics. `FinancialFactService` owns SEC ingestion, source identity, acceptance-aware `known_at`, and as-of retrieval. `NormalizedMetricsService` owns versioned concept precedence, unit conversion, annual/quarterly/TTM construction, derived calculations, warnings, and source-fact lineage. API routes do not perform financial normalization.

`CompanyIntelligenceService` is the V3 orchestration boundary. The router only validates strict query models, maps typed domain results to explicit camelCase response schemas, and translates lookup/validation failures into HTTP semantics. No Company Intelligence calculation is implemented inside API routes, and V2 stock/option route contracts remain unchanged.

`EvidenceService` is the source-traceability boundary underneath that orchestrator. `EvidenceRepository` versions public documents, preserves exact source spans, and links those spans to typed claims. Relationship, segment, KPI, and guidance modules may depend on this layer, but they may not persist a sourced claim without inspectable evidence. See [Evidence Intelligence](evidence-intelligence.md).

`RelationshipService` owns conservative explicit-text extraction, counterparty resolution, perspective direction, current-network reads, and auditable overrides. `OperationsIntelligenceService` owns version-aware mix and growth, while `GuidanceService` owns immutable revisions and deterministic outcome reconciliation. Their repositories persist domain records and generic evidence links; API routes only validate and serialize. See [Business Network](business-network.md), [Operating Intelligence](operating-intelligence.md), and [Guidance Intelligence](guidance-intelligence.md).

Hosted authentication is intentionally absent. Storage tables allow nullable `owner_id` so repository logic can later support users without contaminating domain models.

See [System Diagrams](system-diagrams.md) for runtime, frontend state, request sequence, DuckDB, and build-fallback views.
