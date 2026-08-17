# S&P 500 Research Universe Cache

## Business Definition

The research-universe cache lets a local user download current S&P 500 membership and prepare enough company research to move from Market Pulse into Company Intelligence. It is a convenience cache for personal research, not a licensed index feed, a historical constituent database, or evidence that a company belonged to the index on an earlier date.

Market Pulse uses the cache to answer:

- Which current constituents belong to a selected GICS sector?
- Which cached constituents gained or lost most in the latest observed session?
- How large are companies relative to one another using point-in-time diluted shares when available?
- Which members are complete, partial, failed, stale, or not downloaded?

The workflow never converts current membership into a backtest universe. Historical portfolio research requires publication-aware membership data that the initial free provider does not supply.

## Modules And Functions

| Module | Responsibility |
| --- | --- |
| `gbb_terminal.universe.models` | Strict snapshot, refresh, cache, status, and sector-response contracts. |
| `gbb_terminal.universe.providers` | Provider-neutral `UniverseProvider` plus the current Wikipedia S&P 500 adapter. |
| `gbb_terminal.universe.repository` | Versioned snapshots, constituent links, per-run diagnostics, and current-snapshot cache reads. |
| `gbb_terminal.universe.service` | Bounded download, retries, resume, cancellation, company research preparation, and sector ranking. |
| `gbb_terminal.api.routes.universes` | V3 status, refresh-job, cancellation, and sector-constituent APIs. |

`WikipediaSP500Provider.fetch_snapshot()` parses the table identified as `constituents`, requires its expected schema, refuses fewer than 400 valid rows, normalizes provider ticker punctuation for Yahoo compatibility, and fingerprints canonical content. A repeated fingerprint reuses the existing snapshot; changed membership appends a new version.

`UniverseResearchService.refresh()` performs these stages:

1. Fetch or explicitly reuse the newest local current-composition snapshot.
2. Resolve every member through normalized CIK and link it to stable `company_id` identity.
3. Skip complete cache records younger than `fresh_hours`, unless `force` is selected.
4. Download three-year Yahoo OHLCV, SEC Company Facts, and SEC submissions with bounded concurrency and retries.
5. Persist raw payloads, vectorized point-in-time facts, normalized metric availability, weekly valuation history, earnings context, latest daily movement, and calculated market capitalization.
6. Persist one terminal state per constituent and a resumable refresh summary.

Provider downloads may overlap, but DuckDB writes remain serialized through one local connection. A company failure does not abort successful peers. Unexpected calculation or persistence errors become failed constituent items; queued or running items are reconciled to failed before a parent run can finish. Cooperative cancellation preserves completed work.

## Current Public Source

The initial provider uses the public Wikipedia S&P 500 constituent table because no free official S&P membership API is available for this open-source scope. Every snapshot retains:

- source and source URL;
- observation date;
- `known_at` and retrieval timestamps;
- content hash and local version;
- source ticker and provider-normalized ticker;
- CIK, company name, GICS sector, sub-industry, and source metadata;
- warnings that the snapshot is current composition only.

Membership changes become known when the source is retrieved. The application does not infer exact historical effective times from this snapshot.

## Cache And Resume Semantics

The latest snapshot is the active Market Pulse universe. Cache counts are scoped to that snapshot, so removed members do not inflate current coverage. Existing company history is not deleted when membership changes.

Constituent states are:

- `completed`: price history and normalized financial availability were prepared without provider errors;
- `partial`: at least one useful dataset was retained while another provider or calculation was unavailable;
- `failed`: neither sufficient price nor financial research completed, or processing failed;
- `skipped`: a fresh complete local record was reused;
- `cancelled`: work stopped cooperatively before persistence;
- `queued` or `running`: transient states that may appear only during an active job.

Run the complete local workflow or a bounded development check with:

```bash
gbb-terminal universe refresh sp500
gbb-terminal universe refresh sp500 --max-companies 5 --concurrency 2
gbb-terminal universe status sp500
```

Use `--force` to ignore freshness, `--fresh-hours` to change resume policy, and `--no-snapshot-refresh` to reuse the latest local membership snapshot. A complete public-data refresh may take substantial time; progress, cancellation, retries, partial results, and later resume are intentional product behavior.

## Market Pulse Presentation

Selecting a sector card stays inside Market Pulse and expands current constituents. The visual treemap uses calculated point-in-time market capitalization for area and latest cached daily return for direction color. Companies without market capitalization use a separately labelled, dashed equal-area region instead of an invented value. The full keyboard-accessible table remains available alongside top-20 gainer and loser lists.

The treemap is descriptive. Rectangle size, daily color, and rankings are not recommendations or forecasts. Observation dates and incomplete coverage remain visible.

## API

| Endpoint | Definition |
| --- | --- |
| `GET /api/v3/universes/sp500` | Current snapshot summary, current-snapshot cache coverage, latest refresh summary, and warnings. |
| `POST /api/v3/universes/sp500/refresh` | Start a persisted, cancellable local refresh job. |
| `GET /api/v3/universes/sp500/sectors/{sector_symbol}/constituents` | Return all selected-sector members, top daily gainers/losers, unavailable rows, market-cap source, and timing. |
| `GET /api/v3/universe-jobs/{job_id}` | Poll local progress and the terminal refresh result. |
| `POST /api/v3/universe-jobs/{job_id}/cancel` | Request cooperative cancellation. |

Request fields use camelCase at the API boundary. `maxCompanies` is a bounded testing and recovery aid, not a different universe definition.
