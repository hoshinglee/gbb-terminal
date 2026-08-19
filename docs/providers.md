# Public Data Providers

Every provider returns a `DataEnvelope` containing dataset, symbol, observation time, `known_at`, retrieval time, delayed/realtime status, source, quality warnings, quota when available, and cache state.

- `YahooProvider`: adjusted daily equities/ETFs and current option chains.
- `SECProvider`: current CIK/company/ticker/exchange associations, current and historical EDGAR submissions, filing indexes and archive documents, company facts, parsed 13F information tables, parsed Form 4 transactions, and filing acceptance timestamps.
- `FINRAProvider`: daily Regulation SHO short-sale volume with an explicit warning that it is not short interest.
- `FREDProvider`: macroeconomic CSV series with revision warnings.
- `OCCProvider`: official aggregate volume/open-interest report catalogue, never represented as historical contract pricing.
- `EstimateProvider`: provider-neutral protocol for timestamped revenue/EPS expectations. Release 0.8 ships only an ignored local/manual fixture adapter and an empty provider; it does not scrape or select a commercial vendor.
- `UniverseProvider`: provider-neutral current-membership snapshot protocol. The initial Wikipedia adapter supplies current S&P 500 composition with explicit non-historical warnings; it is not an official or licensed S&P feed.

`MarketData` first checks fresh DuckDB data. Provider requests use bounded retries and exponential backoff. If retrieval fails, the service returns a stale cache with warnings when possible; otherwise it reports a provider error.

Point-in-time consumers must filter on `known_at`, not report-period or observation labels. A 13F record becomes available at SEC filing acceptance. FINRA short interest and daily short-sale volume remain separate datasets.

The SEC company-ticker directory is periodically updated current-association data, not a historical security master. Company Identity persists its accuracy/scope warning and requires explicit effective dates for ticker-change history rather than backdating the latest directory snapshot.

SEC Company Facts ingestion stores every numeric annual and quarterly observation instead of selecting only the latest concept value. Submission acceptance timestamps are joined by accession when available; otherwise the fact uses a visible, conservative end-of-filed-date `known_at` fallback. The raw Company Facts and submissions payloads remain in `provider_cache` alongside the normalized point-in-time rows.

Public routes under `/api/v2/public-data` expose SEC filings/fundamentals/13F/Form 4, FINRA daily short-sale volume, FRED series, and OCC report context. Responses include metadata and fall back to the corresponding cached provider payload when retrieval fails.

The separate V3 estimates route reads a configured manual fixture through the provider protocol. Estimate coverage is optional and is never substituted for SEC-reported history. See [Analyst Estimates Provider Contract](analyst-estimates.md).

SEC archive requests use a provider-level throttle, bounded exponential retries, and `Retry-After` when supplied. Filing acceptance—not report date—sets document `known_at`. See [Public Document Collection](public-document-collection.md).

S&P 500 universe refreshes use bounded concurrent downloads, serialized DuckDB persistence, per-company terminal diagnostics, freshness-based resume, and stale provider-cache fallback. See [S&P 500 Research Universe Cache](universe-cache.md).
