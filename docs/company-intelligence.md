# Company Intelligence

Source: `src/gbb_terminal/intelligence/`

Company Intelligence studies a business through a durable `company_id`. Market workflows still use tickers because prices and option contracts belong to securities. The identity layer resolves those ticker symbols to a company before future fundamentals, earnings, valuation, document, or relationship queries are performed.

## Business Definitions

| Concept | Definition |
| --- | --- |
| Company | The durable business/filer identity represented by `company_id` and normalized SEC CIK. |
| Security mapping | A ticker and exchange association valid for a bounded period. A company may have multiple share classes or historical tickers. |
| Primary ticker | The security selected as the current default for navigation. It does not define company identity. |
| Provenance | Source, dataset, observation time, `known_at`, retrieval time, status, cache state, and quality warnings attached to an identity observation. |

## Canonical Models

`CompanyIdentity` contains:

- Stable `company_id` and ten-digit CIK.
- Legal name, optional sector, industry, and fiscal-year end.
- Active/inactive company status.
- Current or latest primary ticker and exchange for display/navigation.
- Every historical `SecurityMapping` and its validity period.
- Latest company-level provenance and per-mapping provenance.

`CompanyRegistration` is a strict Pydantic command. Unknown fields are rejected, ticker/CIK/exchange/fiscal-year-end values are normalized, and provenance timestamps must include a timezone.

## Resolution And Update Rules

- `CompanyIdentityService.resolve_ticker()` resolves the active mapping first and can resolve the latest historical mapping for a delisted ticker.
- `CompanyIdentityService.resolve_cik()` resolves the same canonical company directly from a normalized CIK.
- Registering the same CIK and ticker updates metadata without changing `company_id` or creating another security row.
- An active ticker cannot belong to two companies. Conflicting registrations fail instead of silently merging identities.
- `change_primary_ticker()` closes the prior mapping on the day before the new mapping starts and appends a new mapping.
- `mark_inactive()` closes active mappings without deleting the company or its earlier ticker history.
- A current SEC directory observation may add an alternate security, but it never guesses a ticker-change effective date. Historical changes require an explicit effective date.

## DuckDB Storage

Schema version 6 adds:

- `companies`: one durable company record per normalized CIK.
- `company_security_mappings`: append-safe ticker/exchange validity records linked to `company_id`.

The identity repository uses transactions for registration, ticker changes, and delisting. Existing market-price, strategy, and option tables remain ticker-based and unchanged.

Schema version 7 adds `sec_financial_facts`, an append-safe point-in-time observation store containing:

- Canonical company/CIK, taxonomy, concept, value, raw value, and unit.
- Period start/end, fiscal year/period, filing form, filed date, accession number, and SEC frame.
- Exact acceptance timestamp when available and a conservative end-of-filed-date fallback otherwise.
- Source, dataset, provider status, cache state, retrieval timestamp, quota, warnings, and source metadata.

The stable fact identity includes company, taxonomy/concept/unit, accession, economic period, filing form, fiscal labels, and frame. Repeating the same source observation is idempotent. A later accession for the same economic period remains a separate restatement rather than replacing the earlier value. If acceptance metadata becomes available after initial ingestion, the existing source fact is enriched without creating another observation.

`FinancialFactQuery.as_of` filters on `known_at`. A query for a historical timestamp cannot see a later amendment or restatement even when the later row covers the same fiscal period.

## Normalized Metrics

INT-03 adds a versioned metrics engine over the point-in-time fact store. It supports annual, discrete-quarterly, and rolling TTM views; deterministic concept precedence; explicit USD/share scaling; missing-input and ambiguity warnings; and source-fact lineage for every non-null result. Derived evidence includes growth, margins, free cash flow, ROE, ROIC, net debt, and share dilution when the required observations exist.

See [Normalized Financial Metrics](financial-metrics.md) for business definitions and function contracts.

## Historical Valuation

INT-05 adds daily or weekly historical trailing valuation using adjusted security closes and normalized facts known at each US market close. The engine exposes P/E, P/S, P/B, EV/Revenue, EV/EBITDA when supported, P/FCF, earnings yield, and FCF yield with explicit `nm` and unavailable states. Every point retains the fundamental period, `known_at`, source fact IDs, and price source.

See [Historical Point-In-Time Valuation](historical-valuation.md) for deterministic alignment, formulas, statistics, and DuckDB cache behavior.

## Earnings Events

INT-06 persists first-class fiscal events with stable identity, SEC filing evidence, timing quality, normalized reported metrics, and session-aware market reactions. Before-open, after-close, weekend/holiday, intraday, and unknown-time events have deterministic anchor rules. D0 through D+60, benchmark adjustment, abnormal volume, reaction paths, and aggregate sample sizes remain reproducible and warning-rich.

See [Earnings Events And Reaction Analytics](earnings-intelligence.md) for window definitions and limitations.

## Analyst Estimate Boundary

INT-08 defines a vendor-neutral revenue/EPS estimate contract and optional local fixture adapter. Expectations retain provider and `known_at`, map to reported metrics only by exact fiscal identity, and remain visually/API-distinct from SEC facts. Missing coverage returns an empty, warning-rich result rather than breaking company, financial, valuation, or earnings workflows.

See [Analyst Estimates Provider Contract](analyst-estimates.md) for fixture configuration, revision semantics, and mapping statuses.

## SEC Directory Sync

The SEC publishes a periodically updated CIK, company-name, ticker, and exchange association file. The SEC states that its accuracy and scope are not guaranteed, so GBB preserves that warning in every ingested mapping and does not treat the retrieval date as a proven historical listing date.

After editable installation, synchronize the current directory with:

```bash
python scripts/sync_company_identities.py
```

The command respects `GBB_DATABASE_PATH` and `GBB_DATA_CONTACT`. Repeated synchronization is idempotent for unchanged CIK/ticker/exchange associations.

After the identity exists, synchronize complete SEC Company Facts and filing acceptance metadata with:

```bash
python scripts/sync_company_facts.py NVDA
```

The raw Company Facts and submissions payloads also remain in `provider_cache`. A provider outage can reuse that cache without deleting or rewriting already persisted fact observations.

## Current Boundary

Release 0.8 extends the strict V3 boundary with historical valuation while preserving the Release 0.7 company overview, point-in-time facts, and normalized metrics contracts. Existing V2 stock, strategy, and option APIs continue accepting tickers unchanged.

See [API Application](api.md) for exact V3 endpoints, filters, response counts, provenance, error semantics, and the company-versus-security boundary.

Official source: [SEC Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).
