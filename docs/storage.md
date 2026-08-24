# DuckDB Storage

Source: `src/gbb_terminal/storage/database.py`

DuckDB is the local system of record and analytical cache. `LocalMarketStore` creates missing tables and adds backward-compatible columns without deleting existing `data/gbb_terminal.duckdb` records.

Price-history writes merge observations by `(symbol, price_date)` instead of deleting older rows. This preserves a previously collected maximum-history series when a later short-window request refreshes recent sessions. `period=max` accepts the complete locally observed listing history without assuming the security existed for an arbitrary 100-year window.

| Table | Purpose |
| --- | --- |
| `price_history` | Cached daily OHLCV by symbol and observation date. |
| `option_chains` | Latest normalized chain for fast loading. |
| `option_chain_snapshots` | One current-chain snapshot per symbol, expiry, and local day. |
| `option_simulation_runs` | Immutable validated request, complete result, provenance, model version, and creation time for every Option Lab run. |
| `provider_cache` | Public-data payload plus observation, known-at, and retrieval metadata. |
| `companies` | Durable company identity keyed by `company_id`, with unique normalized CIK and latest metadata provenance. |
| `company_security_mappings` | Time-bounded ticker/exchange mappings, primary-security state, and mapping-level provenance. |
| `sec_financial_facts` | Append-safe SEC/XBRL observations with accession identity, economic periods, `known_at`, and complete provider context. |
| `valuation_series` | Versioned daily/weekly trailing valuation points with price, denominator, point-in-time fact lineage, status, and warnings. |
| `earnings_events` | Stable fiscal events with announcement timing, SEC evidence, reported metrics, and quality warnings. |
| `earnings_reactions` | Deterministic benchmark-specific event windows, reaction paths, volume context, and engine version. |
| `evidence_documents` | Versioned public documents with source identity, publication-aware timing, content fingerprint, provenance, and parse state. |
| `evidence_spans` | Independently retrievable exact source text with document location and extraction metadata. |
| `evidence_claim_links` | Additive support, context, or contradiction links between typed claims and source spans. |
| `evidence_document_contents` | Verified raw source bytes, parser version, storage time, and successful parse time for each immutable evidence version. |
| `intelligence_refresh_runs` | SEC refresh request, terminal state, source/module counts, coverage, warnings, and timestamps. |
| `intelligence_refresh_items` | Per-document unchanged, parsed, unsupported, failed, extraction-failed, or no-disclosure diagnostics. |
| `universe_snapshots` | Versioned current-composition source snapshots with content hash, timing, provenance, and limitations. |
| `universe_constituents` | Snapshot-specific ticker, CIK, GICS classification, source metadata, and optional stable company link. |
| `universe_refresh_runs` | Bulk profile request, coverage counts, terminal state, warnings, and timestamps. |
| `universe_refresh_items` | Per-company queued/running/completed/partial/failed/skipped/cancelled state and prepared-data counts. |
| `universe_company_cache` | Current local price, daily move, point-in-time market cap, source timing, quality warnings, and profile coverage. |
| `business_relationships` | Stable economic edges keyed by source company, normalized counterparty, type, and direction. |
| `relationship_observations` | Append-only resolution, exposure, validity, confidence, extraction, and override history for relationship edges. |
| `operating_metric_definitions` | Versioned segment, geography, and KPI definitions with reporting basis and evidence. |
| `operating_metric_observations` | Point-in-time issuer operating values with fiscal period, unit, extraction method, and evidence. |
| `guidance_statements` | Immutable exact guidance/commitment wording, normalized value semantics, applicable period, and revision links. |
| `guidance_evaluations` | Append-only delivered/missed/withdrawn/superseded outcomes with method and source-fact lineage. |
| `portfolio_contexts` | Local investable value, liquid cash, USD base currency, and future-compatible nullable owner identity. |
| `portfolio_positions` | Manual signed holdings, cost basis, optional manual market value, notes, and optional stable company identity. |
| `risk_policies` | Immutable versioned personal position, assignment, collateral, cash-reserve, and stress-loss limits. |
| `risk_policy_snapshots` | Stable complete policy payloads attachable to future research and decision records. |
| `decision_theses` | Immutable company-scoped thesis versions with user-owned status and resolved source evidence. |
| `decision_thesis_snapshots` | Explicit stable thesis payloads that remain unchanged after later thesis edits. |
| `decision_position_intents` | Versioned target/maximum company exposure plus derived current portfolio context. |
| `decision_entry_plans` | Versioned instrument expression, execution mode, escape rule, staged tranches, and allocation reserve. |
| `decision_journal` | Current complete decision record with frozen thesis, policy, intent, expression, and entry-plan snapshots. |
| `decision_journal_revisions` | Append-only complete historical revisions saved before each journal update. |
| `strategy_catalogue` | Canonical JSON/legacy YAML, family, template version, and hidden semantic key. |
| `backtest_runs`, `backtest_trades` | Legacy run summaries and closed trade records. |
| `research_runs` | Immutable Strategy V2, data snapshot, validation, tested settings, and results. |
| `option_positions` | Current complete paper-position state with nullable future `owner_id`. |
| `option_position_events` | Append-only lifecycle event payload and state-after snapshot. |
| `local_jobs` | Replaceable local progress/cancellation storage for long research work. |

`save_strategy()` updates an existing semantic identity instead of creating a duplicate. V2 strategy identity includes the template version, parameter values, and risk definition; it excludes ticker, universe, benchmark, timeframe, execution assumptions, display name, and description. Those research inputs live in `research_design` and contribute to the separate research-run reproducibility key. Keys remain internal because they are reproducibility metadata, not user decisions.

Every requested ticker/expiry chain is cached independently. Loading a later expiry never replaces the symbol's default nearest-expiry cache. Every option simulation is append-only and may be reloaded independently of a paper position. Paper positions optionally store `research_run_id`, and every lifecycle event is written transactionally with the resulting position state. The ledger can therefore reconcile premium cash, signed shares, share basis, contracts, collateral, realized P&L, and current structure after close, roll, share trade, added leg, exercise, expiry, or assignment.

Company identity is independent of market-data symbol caches. `companies` retains the durable business key and `company_security_mappings` appends dated ticker/exchange associations. Duplicate CIK registration updates the existing company, active ticker conflicts are rejected, and ticker changes or delistings close mappings rather than deleting them. Schema version 6 creates these tables without rewriting existing price, strategy, option, or provider records.

Schema version 7 adds `sec_financial_facts`. Stable accession-based identities deduplicate repeated downloads while preserving later restatements as separate rows. Historical reads filter `known_at`; source accession, filing, period, frame, raw unit/value, retrieval status, and quality warnings remain inspectable. Raw SEC payloads continue using `provider_cache` for stale-data fallback.

Schema version 8 adds `valuation_series`. Historical points are replaceable only within the same company, ticker, date, frequency, metric, and engine version. Recalculation under a newer engine version remains distinguishable, and source fact IDs preserve the point-in-time denominator lineage.

Schema version 9 adds `earnings_events` and `earnings_reactions`. Event identity is stable across repeated ingestion; reaction identity includes benchmark and engine version. Source evidence, reported metrics, calculated paths, warnings, and computation timestamps remain inspectable.

Schema version 10 adds `evidence_documents`, `evidence_spans`, and `evidence_claim_links`. Exact duplicate source content is idempotent; changed content under the same company/source/external identity creates a linked version. Failed parses cannot create evidence spans, and claim associations remain additive so one claim can retain multiple supporting or contradicting excerpts.

Schema version 11 adds `business_relationships` and `relationship_observations`. Economic edge identity excludes changing exposure and resolution fields, allowing new evidence and corrections to accumulate without duplicate graph edges. Current reads apply both `known_at` and validity boundaries.

Schema version 12 adds `operating_metric_definitions` and `operating_metric_observations`. Definition changes append explicit versions and supersession links; observations retain exact fiscal period, unit, source timing, and evidence.

Schema version 13 adds `guidance_statements` and `guidance_evaluations`. Original wording and revisions are immutable, while outcomes and withdrawals append auditable evaluation records.

Schema version 14 adds raw evidence content plus Company Intelligence refresh runs and per-document diagnostics. It does not rewrite existing evidence or structured claims.

Schema version 15 adds versioned research-universe snapshots, snapshot membership, resilient bulk-run diagnostics, and the local company-research cache. Cache coverage is read against the active snapshot; removed constituents do not inflate current counts, while their existing company and research history remains intact. Current membership is never written into historical research-run universe identity.

Schema version 16 removes relationship observations produced by the superseded `deterministic_relationship_rules_v2` list grammar, which could classify product categories as counterparties. It removes only those deterministic observations and orphaned edges; source documents, evidence spans, human overrides, and unrelated relationship versions remain intact. The stricter v3 extractor accepts an unambiguous registered company or a disclosed legal-entity name before creating a list-derived edge.

Schema version 17 adds the personal portfolio context, manual positions, immutable risk-policy versions, and policy snapshots. The migration is append-safe and does not rewrite existing research or market data. Manual position persistence does not depend on price-provider availability. A resolved holding stores the stable Company Intelligence `company_id`; an unresolved holding retains its normalized ticker and can be reconciled later without losing user-entered quantities, basis, value, or notes.

Schema version 18 adds Decision Center thesis versions/snapshots, position intents, entry plans, current journal records, and append-only journal revisions. Payloads are validated through typed domain models on write and read. Decision records copy historical component payloads rather than foreign-keying only to mutable current rows, so later thesis, policy, intent, or plan versions cannot rewrite an earlier decision. The option paper ledger remains separate and may be referenced only by its optional position ID.

SEC financial facts are inserted and acceptance metadata is enriched through set-based DuckDB operations. This keeps large public Company Facts payloads append-safe without accumulating one transaction version per row.

Runtime `data/` is excluded from Git.

See [System Diagrams](system-diagrams.md) for the logical DuckDB entity-relationship view and the provider-cache request sequence.
