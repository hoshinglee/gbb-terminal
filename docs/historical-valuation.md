# Historical Point-In-Time Valuation

Sources: `src/gbb_terminal/intelligence/valuation.py`, `valuation_definitions.py`, `valuation_models.py`, and `valuation_repository.py`

Historical valuation combines adjusted security prices with normalized SEC fundamentals that were known at each valuation timestamp. It is an educational trailing-history view, not a target price or recommendation.

## Alignment Rules

- Every valuation date uses the actual US trading session represented by the price row.
- The fundamental boundary is 4:00 p.m. `America/New_York`, converted to UTC with daylight-saving rules.
- A filing accepted after that close cannot affect that session's valuation. It first becomes eligible for the next available trading session.
- Weekly history uses the last observed trading session in each Friday-ending week; it never invents a Friday observation for a holiday.
- TTM flow denominators come from four contiguous normalized quarters available under that session's `known_at` boundary. Cumulative Q2/Q3 cash-flow facts are differenced into discrete quarters, and an omitted Q4 is derived from the fiscal-year value less Q1-Q3.
- Balance-sheet inputs use the latest normalized period available inside the same TTM snapshot.
- Share-count treatment uses the latest quarterly diluted weighted-average observation, with the documented basic-share fallback when diluted shares are absent.
- Later amendments and restatements remain stored, but cannot alter an earlier as-of valuation because every historical snapshot re-applies the fact `known_at` boundary.

## Metric Definitions

| Metric | Definition |
| --- | --- |
| Trailing P/E | Market capitalization / positive TTM net income. |
| Price / Sales | Market capitalization / positive TTM revenue. |
| Price / Book | Market capitalization / positive stockholders' equity. |
| EV / Revenue | Enterprise value / positive TTM revenue. |
| EV / EBITDA | Enterprise value / positive TTM operating income plus depreciation and amortization, when all inputs exist. |
| Price / FCF | Market capitalization / positive TTM free cash flow. |
| Earnings Yield | TTM net income / market capitalization. Negative yields remain visible. |
| FCF Yield | TTM free cash flow / market capitalization. Negative yields remain visible. |

Market capitalization is adjusted close multiplied by point-in-time diluted weighted-average shares. Enterprise value is market capitalization plus debt minus cash. This reproducible research convention may differ from vendor calculations using live basic shares, minority interest, preferred stock, leases, or other adjustments.

Non-positive multiple denominators return `nm` rather than a misleading multiple. Missing shares, cash, debt, or normalized flow inputs return `unavailable` with warnings and source lineage.

## Statistics And Storage

For each selected history window, the service returns the latest available value, empirical percentile, median, minimum, maximum, z-score when dispersion exists, and usable sample size. Statistics exclude `nm` and unavailable observations.

DuckDB schema version 8 adds `valuation_series`. Its key includes company, ticker, actual valuation date, daily/weekly frequency, metric, and engine version. Cached rows retain price, numerator context, denominator, fundamental period, fundamental `known_at`, source fact IDs, warnings, and computation time. A valuation run loads the supported point-in-time fact set once and persists the computed series through a bulk DuckDB relation rather than row-by-row inserts.

## API

`GET /api/v3/companies/{ticker}/valuation`

Query fields:

- `period=1y|3y|5y|10y|max`
- `frequency=daily|weekly`
- optional comma-separated `metrics`
- optional timezone-aware `as_of`

The strict V3 response includes history, current-period statistics, engine version, price/fundamental provenance, source fact IDs, and warnings.
