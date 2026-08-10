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

## SEC Directory Sync

The SEC publishes a periodically updated CIK, company-name, ticker, and exchange association file. The SEC states that its accuracy and scope are not guaranteed, so GBB preserves that warning in every ingested mapping and does not treat the retrieval date as a proven historical listing date.

After editable installation, synchronize the current directory with:

```bash
python scripts/sync_company_identities.py
```

The command respects `GBB_DATABASE_PATH` and `GBB_DATA_CONTACT`. Repeated synchronization is idempotent for unchanged CIK/ticker/exchange associations.

## Current Boundary

Release 0.7 INT-01 is storage and domain infrastructure. It intentionally does not add Company Intelligence HTTP endpoints or a browser panel. Those contracts belong to INT-04 after point-in-time SEC facts and normalized metrics are available. Existing V2 stock, strategy, and option APIs continue accepting tickers.

Official source: [SEC Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).
