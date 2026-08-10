# API Application

Sources: `src/gbb_terminal/api/main.py`, `src/gbb_terminal/api/routes/`, and `src/gbb_terminal/api/schemas/`

FastAPI is the orchestration boundary. Routes validate requests, call market/domain services, persist immutable records, and return browser-ready data. Calculation logic remains outside the route layer.

## V3 Company Intelligence endpoints

V3 separates company-business research from V2 security-market observability. A ticker in the path is first resolved through the canonical company registry; business facts and metrics are then queried by stable `company_id`.

| Endpoint | Definition |
| --- | --- |
| `GET /api/v3/companies/{ticker}` | Return canonical company metadata, active/latest primary security, complete dated security mappings, and company/mapping provenance. Optional `as_of=YYYY-MM-DD` resolves a historical ticker association. |
| `GET /api/v3/companies/{ticker}/financials` | Return point-in-time SEC fact observations. Optional `concepts`, `forms`, timezone-aware `as_of`, and `limit` filters are applied before serialization. |
| `GET /api/v3/companies/{ticker}/metrics` | Return normalized annual, quarterly, or TTM metrics using `period=annual|quarterly|ttm` and optional timezone-aware `as_of`. |
| `GET /api/v3/companies/{ticker}/valuation` | Return daily or weekly trailing valuation history, statistics, point-in-time fact lineage, and price provenance. |
| `GET /api/v3/companies/{ticker}/earnings` | Return source-backed fiscal events, session-aware D0/D+1/D+5/D+20/D+60 reactions, benchmark adjustment, volume context, and aggregate statistics. |
| `GET /api/v3/companies/{ticker}/estimates` | Return timestamped provider-neutral revenue/EPS expectations, revision observations, exact reported-period mappings, and expectation/reporting provenance. Empty coverage remains a successful response. |

All V3 responses include `apiVersion: "v3"`. Response fields use camelCase; internal Python domain models remain snake_case. V3 query and response schemas reject unknown fields. A missing canonical company returns `404`; invalid filters or domain inputs return `400`; invalid/unknown query parameters return `422`.

Company overview provenance includes source, dataset, observation, `knownAt`, retrieval, provider status, cache state, quota, and quality warnings. Every raw financial fact includes accession, filing, frame, economic period, exact/fallback `knownAt` semantics, raw unit/value, provider context, and source metadata. Metric responses expose `asOf`, definition version, warnings, and the complete set of source fact IDs used by their non-null values. Valuation aligns each adjusted close with only SEC facts known by that US market close; non-positive multiple denominators return `nm`, while missing inputs return `unavailable`. See [Historical Point-In-Time Valuation](historical-valuation.md).

Earnings responses classify SEC acceptance time in New York market hours, align after-close/weekend/holiday events to the next observed session, and preserve date-only ambiguity. They distinguish normalized reported facts from calculated reactions and state that historical reactions do not predict the next event. See [Earnings Events And Reaction Analytics](earnings-intelligence.md).

Estimate responses never represent expectations as SEC facts. Each observation has provider and `knownAt`; fiscal mapping requires exact metric, period end, fiscal year, and fiscal period. The default local provider returns empty coverage unless an ignored manual fixture is configured. See [Analyst Estimates Provider Contract](analyst-estimates.md).

`matchingFactCount` reports all rows matching the financial-history filters; `returnedFactCount` reports rows included under `limit`. Truncation adds an explicit warning rather than silently implying complete history.

V3 does not extend `/api/v2/stocks/{ticker}` with fundamentals. V2 remains the contract for quotes, OHLCV, technical context, and current option-market context. Company Intelligence has no brokerage execution and does not reinterpret a ticker as durable business identity.

## V2 research endpoints

| Endpoint | Definition |
| --- | --- |
| `GET /api/v2/strategy-templates` | Return typed built-in templates and parameter metadata. |
| `POST /api/v2/strategy-proposals` | Translate natural language into a safe proposal and clarification list. |
| `POST /api/v2/strategies` | Validate and deduplicate a canonical `StrategyInstance`. |
| `POST /api/v2/research-runs` | Execute and persist an immutable, fingerprinted single-stock or ranked-portfolio run from a strategy configuration and `research_design`. |
| `GET /api/v2/research-runs/{id}` | Load one persisted run using the same snake-case ResearchRun contract returned at creation. |
| `POST /api/v2/parameter-searches` | Run exhaustive or seeded Optuna walk-forward search, evaluate an untouched final window, and persist the selected run. |
| `GET /api/v2/chart-data` | Return date-aligned OHLCV, indicators, and source metadata. |

## V2 observability endpoints

| Endpoint | Definition |
| --- | --- |
| `GET /api/v2/stocks/{ticker}?period=1y` | Return quote evidence and day/week/month/year OHLCV with technical indicators and provenance. |
| `GET /api/v2/market-overview` | Return SPY context, sector breadth inputs, three-month relative strength, cross-asset proxies, provider status, and generation time. |
| `GET /api/v2/data-providers` | Return configured free-provider adapter status. |
| `GET /api/v2/public-data/*` | Return SEC, FINRA, FRED, or OCC payloads with provider metadata and stale-cache fallback where available. |

Market overview rows are independently available or unavailable. A failed Yahoo symbol returns a visible row-level warning without discarding successful sector and macro rows. Fresh DuckDB price snapshots are labelled `Cached Snapshot`; they retain source, observation, known-at, retrieval, and quality-warning fields.

## V2 option endpoints

| Endpoint | Definition |
| --- | --- |
| `GET /api/v2/options/templates` | Return grouped Recipe V2 metadata, leg roles, and structural policies. |
| `GET /api/v2/options/chains/{ticker}?expiration=YYYY-MM-DD` | Return every provider-reported expiry and every contract for the selected current or cached expiry. |
| `POST /api/v2/options/simulations` | Calculate theoretical evidence and persist an immutable, versioned local simulation run. |
| `GET /api/v2/options/simulations` | List recent immutable simulation runs and their summary evidence. |
| `GET /api/v2/options/simulations/{id}` | Reload one exact simulation request and result. |
| `POST /api/v2/options/positions` | Create a paper-position ledger, optionally linked to its originating simulation run. |
| `GET /api/v2/options/positions` | List recently updated local paper positions for rediscovery after reload. |
| `GET /api/v2/options/positions/{id}` | Return current state and all earlier events. |
| `POST /api/v2/options/positions/{id}/events` | Apply and persist one validated lifecycle transition. |

Option-chain responses include the selected and default expiration, all available expirations, quote provenance, quote-quality warnings, and normalized bid/ask/last/mid/spread, volume, open interest, IV, moneyness, and last-trade fields. An unavailable requested expiry is rejected rather than silently replaced.

Legacy `/api/*` routes remain compatible during migration. `POST /api/strategy/propose` and its V2 counterpart validate provider-authored JSON, return clarification metadata, and expose only server-generated compatibility YAML to the existing backtest flow. Internal semantic keys and YAML are omitted from ordinary catalogue views; advanced export remains available through an intentional future workflow.

V2 request models reject unknown fields. `ResearchDesign` owns ticker/universe, benchmarks, timeframe, and execution assumptions; `StrategyInstance` owns only reusable rule and risk configuration. Relative-strength designs may resolve an automatic sector ETF from Yahoo sector metadata, or use an explicit custom symbol. Research-run responses include internal strategy and reproducibility keys for machine-level replay, but the browser intentionally does not display them in ordinary Strategy Lab views.

Individual-stock research results include an additive `marketChart` object. Its `intervals` map contains `day`, `week`, `month`, and `year` OHLCV points with interval-specific technical indicators and final strategy state for each bar. Ranked-portfolio results return `marketChart: null` because an average of different securities is not a valid tradable candlestick series. The existing `chart` equity-curve contract remains unchanged.

`request_logging_and_local_no_cache` records request IDs, duration, and status. Browser assets receive `Cache-Control: no-store`, preventing confusing conditional-cache responses during local development.
